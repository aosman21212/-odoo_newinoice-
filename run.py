import xmlrpc.client
import requests
import base64
import json
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Processing API",
    description="API for processing invoices and sending them to webhook",
    version="1.0.0"
)

# Odoo connection details
url = 'https://odoo-ps-psae-bab-international-corp-staging-20730869.dev.odoo.com'
db = 'odoo-ps-psae-bab-international-corp-staging-20730869'
username = 'admin'
api_key = 'f76de5f7d8feb704707b8b18eefafc0a4d2fbc5f'  # Your API key
pdf_api_key = 'wEUcUsNSIaz8viGwzA_6VnimKdlgbItusDKMGOmVvmZRH33ptRh4MmcIXdujT-zHL8nGypkK8rIqT5TDsKv7'  # PDF API key

# Authenticate with Odoo
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), allow_none=True)
uid = common.authenticate(db, username, api_key, {})

if not uid:
    print("Authentication failed. Please check your credentials.")
    exit(1)

# Initialize the models endpoint
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), allow_none=True)

# Pydantic models for request/response
class InvoiceRequest(BaseModel):
    invoice_number: str

class InvoiceLine(BaseModel):
    product: str
    quantity: float
    price_unit: float
    subtotal: float

class InvoiceDetails(BaseModel):
    invoice_name: str
    partner: str
    invoice_date: str
    invoice_date_due: str
    amount_total: float
    currency: str
    invoice_lines: List[InvoiceLine]
    attachment_ids: List[Dict[str, Any]] = []

class PartnerLedgerEntry(BaseModel):
    date: str
    name: str
    debit: float
    credit: float
    balance: float

class PartnerLedger(BaseModel):
    partner_id: int
    partner_name: str
    ledger_entries: List[PartnerLedgerEntry]

class PDFInvoice(BaseModel):
    invoice_id: int
    invoice_name: str
    pdf_content: str

class Operation(BaseModel):
    name: str
    payload: Dict[str, Any]

class WebhookPayload(BaseModel):
    event: str
    operations: List[Operation]

class InvoiceResponse(BaseModel):
    success: bool
    message: str
    invoice_details: Optional[InvoiceDetails] = None
    partner_ledger: Optional[PartnerLedger] = None
    pdf_invoice: Optional[PDFInvoice] = None

class AttachmentResponse(BaseModel):
    name: str
    mimetype: str
    content: str
    file_size: int

class EmailRequest(BaseModel):
    invoice_id: int
    template_id: str = "Invoice: Send by email"
    attachment_ids: Optional[List[int]] = None

class EmailResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[int] = None

class EmailTemplateRequest(BaseModel):
    name: str
    model_id: str = "account.move"
    subject: str
    body_html: str
    email_from: str
    email_to: str
    auto_delete: bool = True
    user_signature: bool = True

    def dict(self, *args, **kwargs):
        # Ensure no None values in the dictionary
        data = super().dict(*args, **kwargs)
        return {k: v if v is not None else "" for k, v in data.items()}

class EmailTemplateResponse(BaseModel):
    success: bool
    message: str
    template_id: Optional[int] = None

class PDFUrlResponse(BaseModel):
    success: bool
    message: str
    pdf_url: Optional[str] = None
    invoice_name: Optional[str] = None
    invoice_type: Optional[str] = None

def get_invoice_by_number(invoice_number):
    """
    Gets a single invoice by its invoice number for company_id 5
    """
    try:
        # Search for invoice with the given number in company_id 5
        invoices = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[
                ['name', '=', invoice_number],
                ['company_id', '=', 5],
                ['move_type', 'in', ['out_invoice', 'in_invoice']]
            ]],
            {
                'fields': ['id', 'name', 'state', 'move_type', 'amount_total', 'create_date']
            }
        )
        
        if not invoices:
            print(f"No invoice found with number: {invoice_number}")
            return None
            
        invoice = invoices[0]
        print(f"\nFound invoice:")
        print("------------------------")
        print(f"ID: {invoice['id']} | Name: {invoice['name']} | Type: {invoice['move_type']} | State: {invoice['state']} | Amount: {invoice['amount_total']} | Created: {invoice['create_date']}")
        
        return invoice
        
    except Exception as e:
        print("Error getting invoice:", str(e))
        return None

def process_invoice(invoice_id):
    """
    Process a single invoice by sending it to the webhook
    """
    try:
        print(f"\nProcessing invoice ID: {invoice_id}")
        send_invoice_to_webhook(invoice_id)
        return True
    except Exception as e:
        print(f"Error processing invoice {invoice_id}: {str(e)}")
        return False

def get_todays_invoices():
    """
    Gets all invoices created today for company_id 5
    """
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Search for invoices created today in company_id 5
        invoices = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[
                ['company_id', '=', 5],
                ['move_type', 'in', ['out_invoice', 'in_invoice']],
                ['create_date', '>=', today],
                ['create_date', '<', tomorrow]
            ]],
            {
                'fields': ['id', 'name', 'state', 'move_type', 'amount_total', 'create_date'],
                'order': 'create_date asc'  # Order by creation date ascending
            }
        )
        
        if not invoices:
            print(f"No invoices found for today ({today})")
            return None
            
        print(f"\nInvoices for today ({today}):")
        print("------------------------")
        for inv in invoices:
            print(f"ID: {inv['id']} | Name: {inv['name']} | Type: {inv['move_type']} | State: {inv['state']} | Amount: {inv['amount_total']} | Created: {inv['create_date']}")
        
        return invoices
        
    except Exception as e:
        print("Error listing today's invoices:", str(e))
        return None

def list_available_invoices():
    """
    Lists all available invoices for company_id 5
    """
    try:
        # Search for invoices in company_id 5
        invoices = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['company_id', '=', 5], ['move_type', 'in', ['out_invoice', 'in_invoice']]]],
            {
                'fields': ['id', 'name', 'state', 'move_type', 'amount_total'],
                'limit': 10  # Limit to 10 invoices for display
            }
        )
        
        if not invoices:
            print("No invoices found for company_id 5")
            return None
            
        print("\nAvailable Invoices:")
        print("------------------")
        for inv in invoices:
            print(f"ID: {inv['id']} | Name: {inv['name']} | Type: {inv['move_type']} | State: {inv['state']} | Amount: {inv['amount_total']}")
        
        return invoices
        
    except Exception as e:
        print("Error listing invoices:", str(e))
        return None

def get_invoice_pdf_url(invoice_id: int) -> dict:
    """
    Gets the PDF URL for an invoice
    """
    try:
        # Get invoice details first to verify it exists and get the name
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice_id], ['company_id', '=', 5]]],
            {'fields': ['name', 'move_type']}
        )
        
        if not invoice:
            return {
                'success': False,
                'message': f'No invoice found with ID: {invoice_id}',
                'pdf_url': None,
                'invoice_name': None,
                'invoice_type': None
            }
            
        invoice = invoice[0]
        
        # Construct the PDF URL based on invoice type
        if invoice['move_type'] == 'out_invoice':
            report_template = 'studio_customization.studio_report_docume_67b31916-ec11-42bd-8ac0-7dc84926581e'
        elif invoice['move_type'] == 'in_invoice':
            report_template = 'studio_customization.studio_report_docume_67b31916-ec11-42bd-8ac0-7dc84926581e'
        else:
            return {
                'success': False,
                'message': f'Unsupported invoice type: {invoice["move_type"]}',
                'pdf_url': None,
                'invoice_name': invoice['name'],
                'invoice_type': invoice['move_type']
            }

        # Construct the PDF URL
        pdf_url = f"{url}/report/pdf/{report_template}/{invoice_id}"
        
        return {
            'success': True,
            'message': 'PDF URL generated successfully',
            'pdf_url': pdf_url,
            'invoice_name': invoice['name'],
            'invoice_type': invoice['move_type']
        }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Error generating PDF URL: {str(e)}',
            'pdf_url': None,
            'invoice_name': None,
            'invoice_type': None
        }

def get_invoice_pdf(invoice_id):
    """
    Gets the PDF content for an invoice
    """
    try:
        # Get the PDF URL first
        url_result = get_invoice_pdf_url(invoice_id)
        
        if not url_result['success']:
            print(f"Error getting PDF URL: {url_result['message']}")
            return None
            
        pdf_url = url_result['pdf_url']
        print(f"Generated PDF URL: {pdf_url}")
        
        # Set up headers with API key and session
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US',
            'Accept': 'application/pdf',
            'User-Agent': 'Mozilla/5.0'
        }
        
        # Get the PDF content with redirect following
        session = requests.Session()
        response = session.get(pdf_url, headers=headers, allow_redirects=True, verify=True)
        
        if response.status_code in [200, 303]:
            # Get the PDF content
            pdf_content = response.content
            print(f"Successfully retrieved PDF content ({len(pdf_content)} bytes)")
            
            # Verify it's actually a PDF
            if not pdf_content.startswith(b'%PDF'):
                print("Warning: Retrieved content does not appear to be a valid PDF")
                return None
                
            # Convert PDF content to base64 for transmission
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            return pdf_base64
        else:
            print(f"Error getting PDF content: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error getting PDF content: {str(e)}")
        return None

def send_invoice_to_webhook(invoice_id):
    """
    Fetches the invoice details and sends them to the webhook.
    """
    try:
        # First, verify if the invoice exists and is accessible
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice_id], ['company_id', '=', 5]]],
            {
                'fields': [
                    "id",
                    "name",
                    "partner_id",
                    "invoice_date",
                    "invoice_date_due",
                    "amount_total",
                    "amount_residual",
                    "invoice_line_ids",
                    "state",
                    "move_type"
                ]
            }
        )
        
        if not invoice:
            print(f"Error: Invoice ID {invoice_id} not found or not accessible for company_id 5")
            return
            
        invoice = invoice[0]
        print(f"Found invoice: {invoice['name']} (State: {invoice['state']})")

        # Get partner details
        partner = models.execute_kw(
            db, uid, api_key,
            'res.partner', 'search_read',
            [[['id', '=', invoice['partner_id'][0]]]],
            {'fields': ['name']}
        )[0]

        # Get invoice line details
        invoice_lines = models.execute_kw(
            db, uid, api_key,
            'account.move.line', 'search_read',
            [[['id', 'in', invoice['invoice_line_ids']]]],
            {
                'fields': [
                    'name',
                    'quantity',
                    'price_unit',
                    'price_subtotal',
                    'product_id',
                    'currency_id'
                ]
            }
        )

        # Get partner ledger entries
        partner_ledger = get_partner_ledger(invoice['partner_id'][0])

        # Get PDF URL
        pdf_url_result = get_invoice_pdf_url(invoice_id)
        pdf_url = pdf_url_result['pdf_url'] if pdf_url_result['success'] else None

        # Prepare the payload with all invoice information
        payload = {
            "event": "new_invoice",
            "operations": [
                {
                    "name": "fetch_invoice_details",
                    "payload": {
                        "invoice": {
                            "invoice_name": invoice['name'],
                            "partner": partner['name'],
                            "invoice_date": invoice['invoice_date'],
                            "invoice_date_due": invoice['invoice_date_due'],
                            "amount_total": invoice['amount_total'],
                            "amount_residual": invoice['amount_residual'],
                            "currency": invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                            "invoice_lines": [{
                                "product": line['product_id'][1] if line['product_id'] else "",
                                "quantity": line['quantity'],
                                "price_unit": line['price_unit'],
                                "subtotal": line['price_subtotal']
                            } for line in invoice_lines]
                        },
                        "company_id": 5
                    }
                },
                {
                    "name": "payment_reminder",
                    "payload": {
                        "invoice": {
                            "invoice_name": invoice['name'],
                            "partner": partner['name'],
                            "amount_residual": invoice['amount_residual'],
                            "currency": invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                            "invoice_date_due": invoice['invoice_date_due']
                        },
                        "company_id": 5
                    }
                },
                {
                    "name": "partner_ledger",
                    "payload": {
                        "partner_id": invoice['partner_id'][0],
                        "partner_name": partner['name'],
                        "ledger_entries": [{
                            "id": entry['id'],
                            "date": entry['date'],
                            "name": entry['name'],
                            "debit": entry['debit'],
                            "credit": entry['credit'],
                            "balance": entry['balance']
                        } for entry in partner_ledger] if partner_ledger else [],
                        "company_id": 5
                    }
                },
                {
                    "name": "pdf_invoice",
                    "payload": {
                        "invoice_id": invoice['id'],
                        "invoice_name": invoice['name'],
                        "pdf_url": pdf_url,
                        "company_id": 5
                    }
                }
            ]
        }

        # Print the complete payload structure
        print("\nComplete Payload Structure:")
        print("-------------------------")
        print(json.dumps(payload, indent=2))

        # Webhook URL
        webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent'

        # Send the payload to the webhook
        response = requests.post(webhook_url, json=payload)

        # Log the response from the webhook
        print("\nWebhook Response:")
        print("----------------")
        print(f"Status Code: {response.status_code}")
        print("\nResponse Headers:")
        for header, value in response.headers.items():
            print(f"{header}: {value}")
        
        print("\nResponse Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text)

        return payload

    except xmlrpc.client.Fault as e:
        if e.faultCode == 3:  # Access Denied
            print(f"Access Denied: You don't have permission to access invoice {invoice_id}")
            print("Please check:")
            print("1. Your API key has the correct permissions")
            print("2. The invoice exists and is accessible")
            print("3. You have the necessary access rights to generate PDFs")
            print("4. The invoice belongs to company_id 5")
        else:
            print(f"Odoo Error: {e.faultString}")
        return None
    except Exception as e:
        print("Error sending invoice to webhook:", str(e))
        return None

# Example usage: Triggered when an invoice is created
def on_invoice_create(invoice_id):
    """
    This function is called when a new invoice is created.
    It triggers the webhook with the invoice PDF.
    """
    send_invoice_to_webhook(invoice_id)

def view_pdf(pdf_url):
    """
    View PDF details using the API key
    """
    try:
        # Set up headers with API key
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Get the PDF content
        response = requests.get(pdf_url, headers=headers)
        
        if response.status_code == 200:
            print("\nPDF Details:")
            print("-----------")
            print(f"Content Type: {response.headers.get('content-type', 'N/A')}")
            print(f"Content Length: {response.headers.get('content-length', 'N/A')} bytes")
            print(f"PDF URL: {pdf_url}")
            return True
        else:
            print(f"Error viewing PDF: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error viewing PDF: {str(e)}")
        return False

def get_partner_ledger(partner_id):
    """
    Gets the ledger entries for a specific partner with the specified fields
    """
    try:
        # Search for ledger entries for the partner
        ledger_entries = models.execute_kw(
            db, uid, api_key,
            'account.move.line', 'search_read',
            [[
                ['partner_id', '=', partner_id],
                ['company_id', '=', 5]
            ]],
            {
                'fields': [
                    'id',
                    'date',
                    'name',
                    'debit',
                    'credit',
                    'balance'
                ],
                'limit': 100,
                'order': 'date asc'  # Order by date ascending
            }
        )
        
        if not ledger_entries:
            print(f"No ledger entries found for partner ID {partner_id}")
            return None
            
        # Convert entries to ensure proper types
        processed_entries = []
        for entry in ledger_entries:
            processed_entry = {
                'id': entry['id'],
                'date': str(entry['date']),
                'name': str(entry['name']) if entry['name'] else '',  # Convert to string, use empty string if None/False
                'debit': float(entry['debit']),
                'credit': float(entry['credit']),
                'balance': float(entry['balance'])
            }
            processed_entries.append(processed_entry)
            
        # Print the raw JSON response
        print("\nRaw JSON Response:")
        print("-----------------")
        print(json.dumps({
            "jsonrpc": "2.0",
            "result": processed_entries
        }, indent=2))
        
        print("\nPartner Ledger Entries:")
        print("----------------------")
        for entry in processed_entries:
            print(f"ID: {entry['id']} | Date: {entry['date']} | Name: {entry['name']} | Debit: {entry['debit']} | Credit: {entry['credit']} | Balance: {entry['balance']}")
        
        return processed_entries
        
    except Exception as e:
        print("Error getting partner ledger:", str(e))
        return None

def download_attachment(attachment_id):
    """
    Downloads an attachment from Odoo
    """
    try:
        print(f"Attempting to download attachment ID: {attachment_id}")
        
        # Get attachment details and content
        attachment = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'read',
            [[attachment_id]],
            {
                'fields': [
                    'name',
                    'mimetype',
                    'file_size',
                    'datas',
                    'store_fname',
                    'type'
                ]
            }
        )
        
        if not attachment:
            print(f"No attachment found with ID: {attachment_id}")
            return None
            
        attachment = attachment[0]
        print(f"Found attachment: {attachment['name']}")
        
        # Handle both binary and url attachments
        if attachment.get('datas'):
            content = attachment['datas']
            print(f"Retrieved binary content for attachment: {attachment['name']}")
        elif attachment.get('store_fname'):
            # Handle file stored on disk
            content = models.execute_kw(
                db, uid, api_key,
                'ir.attachment', 'get_file',
                [[attachment_id]]
            )
            if content:
                content = base64.b64encode(content).decode('utf-8')
                print(f"Retrieved file content for attachment: {attachment['name']}")
            else:
                print(f"Failed to retrieve file content for attachment: {attachment['name']}")
                return None
        else:
            print(f"No content found for attachment: {attachment['name']}")
            return None
            
        return {
            'name': attachment['name'],
            'mimetype': attachment['mimetype'],
            'content': content,
            'file_size': attachment['file_size']
        }
            
    except xmlrpc.client.Fault as e:
        print(f"Odoo Error downloading attachment: {str(e)}")
        return None
    except Exception as e:
        print(f"Error downloading attachment: {str(e)}")
        return None

@app.get("/download-attachment/{attachment_id}", response_model=AttachmentResponse)
async def download_attachment_endpoint(attachment_id: int):
    """
    Download an attachment by its ID
    """
    try:
        print(f"Received request to download attachment ID: {attachment_id}")
        
        # Validate attachment_id
        if not isinstance(attachment_id, int) or attachment_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid attachment ID. Must be a positive integer."
            )
        
        attachment = download_attachment(attachment_id)
        
        if not attachment:
            raise HTTPException(
                status_code=404,
                detail=f"No attachment found with ID: {attachment_id}"
            )
        
        print(f"Successfully prepared attachment: {attachment['name']}")
        return attachment
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading attachment: {str(e)}"
        )

@app.get("/invoice-attachments/{invoice_id}")
async def get_invoice_attachments_endpoint(invoice_id: int):
    """
    Get all attachments for a specific invoice
    """
    try:
        print(f"Received request to get attachments for invoice ID: {invoice_id}")
        
        # Validate invoice exists
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice_id], ['company_id', '=', 5]]],
            {'fields': ['name']}
        )
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"No invoice found with ID: {invoice_id}"
            )
            
        # Get attachments
        attachments = get_invoice_attachments(invoice_id)
        
        if attachments is None:
            raise HTTPException(
                status_code=500,
                detail="Error fetching attachments"
            )
            
        return {
            "invoice_name": invoice[0]['name'],
            "attachments": attachments
        }
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting attachments: {str(e)}"
        )

@app.get("/")
async def root():
    """Root endpoint to check if API is running"""
    return {"message": "Invoice Processing API is running"}

def generate_curl_command(payload):
    """
    Generates a curl command for the given payload
    """
    json_data = json.dumps(payload)
    curl_command = f"""curl --location --request POST 'https://odoo-agent-main-113251955071.me-central1.run.app/agent' \\
--header 'Content-Type: application/json' \\
--data '{json_data}'"""
    return curl_command

@app.post("/process-invoice")
async def process_invoice_endpoint(request: InvoiceRequest):
    """
    Process an invoice by its invoice number, send to webhook, and send email
    """
    try:
        print(f"\nProcessing invoice number: {request.invoice_number}")
        
        # Get the invoice
        invoice = get_invoice_by_number(request.invoice_number)
        if not invoice:
            print(f"No invoice found with number: {request.invoice_number}")
            raise HTTPException(status_code=404, detail=f"No invoice found with number: {request.invoice_number}")
        
        print(f"Found invoice: {invoice['name']} (ID: {invoice['id']})")
        
        # Get invoice details
        try:
            invoice_details = models.execute_kw(
                db, uid, api_key,
                'account.move', 'search_read',
                [[['id', '=', invoice['id']], ['company_id', '=', 5]]],
                {
                    'fields': [
                        "name",
                        "partner_id",
                        "invoice_date",
                        "invoice_date_due",
                        "amount_total",
                        "amount_residual",
                        "invoice_line_ids",
                        "state",
                        "move_type",
                        "attachment_ids"
                    ]
                }
            )
            
            if not invoice_details:
                print(f"Failed to get invoice details for ID: {invoice['id']}")
                raise HTTPException(status_code=500, detail=f"Failed to get invoice details for: {invoice['name']}")
            
            invoice_details = invoice_details[0]
            print(f"Got invoice details for: {invoice_details['name']}")
            
            # Get all attachments
            all_attachment_ids = []
            if invoice_details.get('attachment_ids'):
                all_attachment_ids.extend(invoice_details['attachment_ids'])
            
            # Get attachment details
            attachments = []
            if all_attachment_ids:
                attachments = models.execute_kw(
                    db, uid, api_key,
                    'ir.attachment', 'search_read',
                    [[['id', 'in', all_attachment_ids]]],
                    {
                        'fields': [
                            'id',
                            'name',
                            'mimetype',
                            'file_size',
                            'create_date',
                            'write_date',
                            'res_model',
                            'res_id',
                            'type',
                            'url'
                        ]
                    }
                )
                print(f"Found {len(attachments)} attachments")
            
        except Exception as e:
            print(f"Error getting invoice details: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting invoice details: {str(e)}")

        # Get partner details
        try:
            partner = models.execute_kw(
                db, uid, api_key,
                'res.partner', 'search_read',
                [[['id', '=', invoice_details['partner_id'][0]]]],
                {'fields': ['name', 'email']}
            )
            
            if not partner:
                print(f"Failed to get partner details for ID: {invoice_details['partner_id'][0]}")
                raise HTTPException(status_code=500, detail=f"Failed to get partner details for invoice: {invoice_details['name']}")
            
            partner = partner[0]
            print(f"Got partner details: {partner['name']}")
            
        except Exception as e:
            print(f"Error getting partner details: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting partner details: {str(e)}")
        
        # Get invoice lines
        try:
            invoice_lines = models.execute_kw(
                db, uid, api_key,
                'account.move.line', 'search_read',
                [[['id', 'in', invoice_details['invoice_line_ids']]]],
                {
                    'fields': [
                        'name',
                        'quantity',
                        'price_unit',
                        'price_subtotal',
                        'product_id',
                        'currency_id'
                    ]
                }
            )
            print(f"Got {len(invoice_lines)} invoice lines")
            
        except Exception as e:
            print(f"Error getting invoice lines: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting invoice lines: {str(e)}")
        
        # Get partner ledger
        try:
            partner_ledger = get_partner_ledger(invoice_details['partner_id'][0])
            print(f"Got {len(partner_ledger) if partner_ledger else 0} ledger entries")
            
        except Exception as e:
            print(f"Error getting partner ledger: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting partner ledger: {str(e)}")
        
        # Get PDF URL and content
        try:
            pdf_url_result = get_invoice_pdf_url(invoice['id'])
            pdf_url = pdf_url_result['pdf_url'] if pdf_url_result['success'] else None
            print(f"Got PDF URL: {pdf_url}")
            
            # Download PDF content
            if pdf_url:
                headers = {
                    'X-API-Key': pdf_api_key,
                    'Cookie': 'frontend_lang=en_US'
                }
                pdf_response = requests.get(pdf_url, headers=headers)
                if pdf_response.status_code == 200:
                    pdf_content = base64.b64encode(pdf_response.content).decode('utf-8')
                    print("Successfully downloaded PDF content")
                else:
                    print(f"Failed to download PDF content: {pdf_response.status_code}")
                    pdf_content = None
            else:
                pdf_content = None
                
        except Exception as e:
            print(f"Error getting PDF content: {str(e)}")
            pdf_content = None

        # Prepare payload
        try:
            payload = {
                "event": "new_invoice",
                "operations": [
                    {
                        "name": "fetch_invoice_details",
                        "payload": {
                            "invoice": {
                                "invoice_name": invoice_details['name'],
                                "partner": partner['name'],
                                "invoice_date": invoice_details['invoice_date'],
                                "invoice_date_due": invoice_details['invoice_date_due'],
                                "amount_total": invoice_details['amount_total'],
                                "amount_residual": invoice_details['amount_residual'],
                                "currency": invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                                "invoice_lines": [{
                                    "product": line['product_id'][1] if line['product_id'] else "",
                                    "quantity": line['quantity'],
                                    "price_unit": line['price_unit'],
                                    "subtotal": line['price_subtotal']
                                } for line in invoice_lines],
                                "attachments": [{
                                    "id": att['id'],
                                    "name": att['name'],
                                    "mimetype": att['mimetype'],
                                    "file_size": att['file_size'],
                                    "create_date": att['create_date'],
                                    "write_date": att['write_date'],
                                    "type": att['type'],
                                    "url": att['url'] if att.get('url') else None
                                } for att in attachments]
                            },
                            "company_id": 5
                        }
                    },
                    {
                        "name": "payment_reminder",
                        "payload": {
                            "invoice": {
                                "invoice_name": invoice_details['name'],
                                "partner": partner['name'],
                                "amount_residual": invoice_details['amount_residual'],
                                "currency": invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                                "invoice_date_due": invoice_details['invoice_date_due']
                            },
                            "company_id": 5
                        }
                    },
                    {
                        "name": "partner_ledger",
                        "payload": {
                            "partner_id": invoice_details['partner_id'][0],
                            "partner_name": partner['name'],
                            "ledger_entries": [{
                                "id": entry['id'],
                                "date": entry['date'],
                                "name": entry['name'],
                                "debit": entry['debit'],
                                "credit": entry['credit'],
                                "balance": entry['balance']
                            } for entry in partner_ledger] if partner_ledger else [],
                            "company_id": 5
                        }
                    },
                    {
                        "name": "pdf_invoice",
                        "payload": {
                            "invoice_id": invoice['id'],
                            "invoice_name": invoice['name'],
                            "pdf_url": pdf_url,
                            "company_id": 5
                        }
                    }
                ]
            }
            
            # Send to webhook
            webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent'
            response = requests.post(webhook_url, json=payload)
            webhook_response = response.json() if response.text else response.text
            
            # Send email if webhook response contains email data
            if isinstance(webhook_response, dict) and 'subject' in webhook_response and 'body' in webhook_response:
                try:
                    # Ensure we have valid email content
                    email_subject = webhook_response.get('subject', '')
                    email_body = webhook_response.get('html', webhook_response.get('body', ''))
                    partner_email = partner.get('email', '')
                    
                    if not partner_email:
                        print("No email address found for partner")
                        return {
                            "webhook_response": webhook_response,
                            "status_code": response.status_code,
                            "payload": payload,
                            "email_status": "No email address found for partner"
                        }
                    
                    # Filter attachments that start with "INV/" or are named "BAB_Invoice22.pdf"
                    inv_attachments = [att for att in attachments if att['name'].startswith('INV/') or att['name'] == 'BAB_Invoice22.pdf']
                    print(f"Found {len(inv_attachments)} attachments (INV/ and BAB_Invoice22.pdf)")
                    
                    # Create and send email with filtered attachments
                    try:
                        # Create the email
                        mail_values = {
                            'email_from': "noreply@babinternational.com",
                            'email_to': partner_email,
                            'subject': email_subject or "",
                            'body_html': email_body or "",
                            'auto_delete': True,
                            'attachment_ids': [(4, att['id']) for att in inv_attachments]  # Add filtered attachments
                        }
                        
                        print(f"Creating email with {len(inv_attachments)} attachments")
                        print("Attachments to be included:")
                        for att in inv_attachments:
                            print(f"- {att['name']}")
                        mail_id = models.execute_kw(
                            db, uid, api_key,
                            'mail.mail', 'create',
                            [mail_values]
                        )
                        
                        # Send the email
                        models.execute_kw(
                            db, uid, api_key,
                            'mail.mail', 'send',
                            [[mail_id]]
                        )
                        print(f"Email sent successfully with ID: {mail_id}")
                        email_status = "Email sent successfully"
                        
                    except Exception as e:
                        print(f"Error creating or sending email: {str(e)}")
                        email_status = f"Error creating or sending email: {str(e)}"
                        
                except Exception as e:
                    print(f"Error preparing email: {str(e)}")
                    email_status = f"Error preparing email: {str(e)}"
            else:
                email_status = "No email data in webhook response"
            
            # Return the webhook response
            return {
                "webhook_response": webhook_response,
                "status_code": response.status_code,
                "payload": payload,
                "email_status": email_status
            }
            
        except Exception as e:
            print(f"Error preparing response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error preparing response: {str(e)}")
            
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def send_email(invoice_id: int, template_id: str, attachment_ids: Optional[List[int]] = None):
    """
    Sends an email using Odoo's mail template system
    """
    try:
        print(f"Attempting to send email for invoice ID: {invoice_id}")
        
        # Get template ID
        template = models.execute_kw(
            db, uid, api_key,
            'mail.template', 'search_read',
            [[['name', '=', template_id]]],
            {'fields': ['id']}
        )
        
        if not template:
            print(f"Template {template_id} not found")
            return {
                'success': False,
                'message': f'Template {template_id} not found',
                'email_id': None
            }
            
        template_id = template[0]['id']
        
        # Prepare context
        context = {
            "default_use_template": True,
            "mark_invoice_as_sent": True,
            "custom_layout": "account.mail_template_data_notification_email_account_invoice",
            "force_email": True
        }
        
        if attachment_ids:
            context["attachment_ids"] = attachment_ids
            
        # Send email using template
        result = models.execute_kw(
            db, uid, api_key,
            'mail.template', 'send_mail',
            [template_id, invoice_id, True],
            {
                'context': context
            }
        )
        
        if result:
            print(f"Successfully sent email for invoice ID: {invoice_id}")
            return {
                'success': True,
                'message': 'Email sent successfully',
                'email_id': result
            }
        else:
            print(f"Failed to send email for invoice ID: {invoice_id}")
            return {
                'success': False,
                'message': 'Failed to send email',
                'email_id': None
            }
            
    except xmlrpc.client.Fault as e:
        print(f"Odoo Error sending email: {str(e)}")
        return {
            'success': False,
            'message': f"Odoo Error: {str(e)}",
            'email_id': None
        }
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}",
            'email_id': None
        }

@app.post("/send-invoice-email", response_model=EmailResponse)
async def send_invoice_email_endpoint(request: EmailRequest):
    """
    Send an email for an invoice using a template
    """
    try:
        print(f"Received request to send email for invoice ID: {request.invoice_id}")
        
        # Validate invoice exists
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', request.invoice_id], ['company_id', '=', 5]]],
            {'fields': ['name']}
        )
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"No invoice found with ID: {request.invoice_id}"
            )
            
        # Send email
        result = send_email(
            request.invoice_id,
            request.template_id,
            request.attachment_ids
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result['message']
            )
            
        return result
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending email: {str(e)}"
        )

def create_email_template(template_data: EmailTemplateRequest):
    """
    Creates a new email template in Odoo
    """
    try:
        print(f"Creating new email template: {template_data.name}")
        
        # Get model ID
        model = models.execute_kw(
            db, uid, api_key,
            'ir.model', 'search_read',
            [[['model', '=', template_data.model_id]]],
            {'fields': ['id']}
        )
        
        if not model:
            return {
                'success': False,
                'message': f'Model {template_data.model_id} not found',
                'template_id': None
            }
            
        model_id = model[0]['id']
        
        # Convert template data to dict and ensure no None values
        template_values = template_data.dict()
        
        # Create template
        template_id = models.execute_kw(
            db, uid, api_key,
            'mail.template', 'create',
            [template_values]
        )
        
        if template_id:
            print(f"Successfully created email template with ID: {template_id}")
            return {
                'success': True,
                'message': 'Email template created successfully',
                'template_id': template_id
            }
        else:
            print("Failed to create email template")
            return {
                'success': False,
                'message': 'Failed to create email template',
                'template_id': None
            }
            
    except xmlrpc.client.Fault as e:
        print(f"Odoo Error creating template: {str(e)}")
        return {
            'success': False,
            'message': f"Odoo Error: {str(e)}",
            'template_id': None
        }
    except Exception as e:
        print(f"Error creating template: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}",
            'template_id': None
        }

@app.post("/create-email-template", response_model=EmailTemplateResponse)
async def create_email_template_endpoint(request: EmailTemplateRequest):
    """
    Create a new email template
    """
    try:
        print(f"Received request to create email template: {request.name}")
        
        result = create_email_template(request)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result['message']
            )
            
        return result
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating email template: {str(e)}"
        )

@app.get("/list-email-templates")
async def list_email_templates():
    """
    List all available email templates
    """
    try:
        templates = models.execute_kw(
            db, uid, api_key,
            'mail.template', 'search_read',
            [[['model_id.model', '=', 'account.move']]],
            {
                'fields': [
                    'id',
                    'name',
                    'subject',
                    'email_from',
                    'email_to',
                    'model_id'
                ]
            }
        )
        
        return {
            "templates": templates
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing email templates: {str(e)}"
        )

@app.get("/invoice-pdf-url/{invoice_id}", response_model=PDFUrlResponse)
async def get_invoice_pdf_url_endpoint(invoice_id: int):
    """
    Get the PDF URL for an invoice
    """
    try:
        print(f"Received request to get PDF URL for invoice ID: {invoice_id}")
        
        result = get_invoice_pdf_url(invoice_id)
        
        if not result['success']:
            raise HTTPException(
                status_code=404 if 'No invoice found' in result['message'] else 500,
                detail=result['message']
            )
            
        return result
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting PDF URL: {str(e)}"
        )

@app.get("/view-invoice-pdf/{invoice_id}")
async def view_invoice_pdf_endpoint(invoice_id: int):
    """
    View the invoice PDF directly in the browser
    """
    try:
        print(f"Received request to view PDF for invoice ID: {invoice_id}")
        
        # Get the PDF URL first
        url_result = get_invoice_pdf_url(invoice_id)
        
        if not url_result['success']:
            raise HTTPException(
                status_code=404 if 'No invoice found' in url_result['message'] else 500,
                detail=url_result['message']
            )
            
        pdf_url = url_result['pdf_url']
        
        # Set up headers with API key and session
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US',
            'Accept': 'application/pdf',
            'User-Agent': 'Mozilla/5.0'
        }
        
        # Get the PDF content with redirect following
        session = requests.Session()
        response = session.get(pdf_url, headers=headers, allow_redirects=True, verify=True, stream=True)
        
        if response.status_code in [200, 303]:
            # Verify content type
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type.lower():
                print(f"Warning: Unexpected content type: {content_type}")
                
            # Return the PDF content as a streaming response
            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename="{url_result["invoice_name"]}.pdf"',
                    'Content-Type': 'application/pdf',
                    'Accept-Ranges': 'bytes'
                }
            )
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error getting PDF content: {response.text}"
            )
            
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error viewing PDF: {str(e)}"
        )

@app.get("/download-invoice-pdf/{invoice_id}")
async def download_invoice_pdf_endpoint(invoice_id: int):
    """
    Download the invoice PDF file
    """
    try:
        print(f"Received request to download PDF for invoice ID: {invoice_id}")
        
        # Get the PDF URL first
        url_result = get_invoice_pdf_url(invoice_id)
        
        if not url_result['success']:
            raise HTTPException(
                status_code=404 if 'No invoice found' in url_result['message'] else 500,
                detail=url_result['message']
            )
            
        pdf_url = url_result['pdf_url']
        
        # Set up headers with API key and session
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US',
            'Accept': 'application/pdf',
            'User-Agent': 'Mozilla/5.0'
        }
        
        # Get the PDF content with redirect following
        session = requests.Session()
        response = session.get(pdf_url, headers=headers, allow_redirects=True, verify=True, stream=True)
        
        if response.status_code in [200, 303]:
            # Verify content type
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type.lower():
                print(f"Warning: Unexpected content type: {content_type}")
                
            # Return the PDF content as a streaming response with download disposition
            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{url_result["invoice_name"]}.pdf"',
                    'Content-Type': 'application/pdf',
                    'Accept-Ranges': 'bytes'
                }
            )
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error getting PDF content: {response.text}"
            )
            
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading PDF: {str(e)}"
        )

def send_email_jsonrpc(invoice_id: int, template_id: str, attachment_ids: Optional[List[int]] = None):
    """
    Sends an email using Odoo's JSON-RPC endpoint
    """
    try:
        print(f"Attempting to send email for invoice ID: {invoice_id}")
        
        # Prepare the JSON-RPC request
        jsonrpc_url = f"{url}/jsonrpc"
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Prepare context
        context = {
            "default_use_template": True,
            "mark_invoice_as_sent": True,
            "custom_layout": "account.mail_template_data_notification_email_account_invoice",
            "force_email": True,
            "attachment_ids": attachment_ids if attachment_ids else []  # Ensure empty list if None
        }
            
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    db,
                    uid,
                    api_key,
                    "mail.template",
                    "send_email",
                    [
                        template_id,
                        invoice_id,
                        True
                    ],
                    {
                        "context": context
                    }
                ]
            }
        }
        
        print("Sending email with payload:", json.dumps(payload, indent=2))
        
        # Send the request
        response = requests.post(jsonrpc_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                print(f"Successfully sent email for invoice ID: {invoice_id}")
                return {
                    'success': True,
                    'message': 'Email sent successfully',
                    'email_id': result['result']
                }
            else:
                print(f"Failed to send email: {result.get('error', {}).get('message', 'Unknown error')}")
                return {
                    'success': False,
                    'message': f"Failed to send email: {result.get('error', {}).get('message', 'Unknown error')}",
                    'email_id': None
                }
        else:
            print(f"Failed to send email: HTTP {response.status_code}")
            return {
                'success': False,
                'message': f"Failed to send email: HTTP {response.status_code}",
                'email_id': None
            }
            
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}",
            'email_id': None
        }

@app.post("/send-invoice-email-jsonrpc", response_model=EmailResponse)
async def send_invoice_email_jsonrpc_endpoint(request: EmailRequest):
    """
    Send an email for an invoice using JSON-RPC endpoint
    """
    try:
        print(f"Received request to send email for invoice ID: {request.invoice_id}")
        
        # Validate invoice exists
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', request.invoice_id], ['company_id', '=', 5]]],
            {'fields': ['name']}
        )
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"No invoice found with ID: {request.invoice_id}"
            )
            
        # Ensure attachment_ids is a list (empty if None)
        attachment_ids = request.attachment_ids if request.attachment_ids is not None else []
            
        # Send email using JSON-RPC
        result = send_email_jsonrpc(
            request.invoice_id,
            request.template_id,
            attachment_ids
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result['message']
            )
            
        return result
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending email: {str(e)}"
        )

def get_invoice_attachments(invoice_id: int):
    """
    Gets all attachments for a specific invoice
    """
    try:
        print(f"Fetching attachments for invoice ID: {invoice_id}")
        
        # Get invoice with attachments
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice_id], ['company_id', '=', 5]]],
            {
                'fields': [
                    'name',
                    'attachment_ids',
                    'message_attachment_ids'
                ]
            }
        )
        
        if not invoice:
            print(f"No invoice found with ID: {invoice_id}")
            return None
            
        invoice = invoice[0]
        print(f"Found invoice: {invoice['name']}")
        
        # Combine both attachment lists
        all_attachment_ids = []
        if invoice.get('attachment_ids'):
            all_attachment_ids.extend(invoice['attachment_ids'])
        if invoice.get('message_attachment_ids'):
            all_attachment_ids.extend(invoice['message_attachment_ids'])
            
        if not all_attachment_ids:
            print("No attachments found for this invoice")
            return []
            
        # Get attachment details
        attachments = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[['id', 'in', all_attachment_ids]]],
            {
                'fields': [
                    'id',
                    'name',
                    'mimetype',
                    'file_size',
                    'create_date',
                    'write_date',
                    'res_model',
                    'res_id',
                    'type',
                    'url'
                ]
            }
        )
        
        print(f"Found {len(attachments)} attachments")
        for attachment in attachments:
            print(f"Attachment: {attachment['name']} ({attachment['mimetype']})")
            
        return attachments
        
    except Exception as e:
        print(f"Error fetching attachments: {str(e)}")
        return None

@app.get("/download-attachment/{attachment_id}")
async def download_attachment_endpoint(attachment_id: int):
    """
    Download a specific attachment
    """
    try:
        print(f"Received request to download attachment ID: {attachment_id}")
        
        # Get attachment details
        attachment = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[['id', '=', attachment_id]]],
            {
                'fields': [
                    'name',
                    'mimetype',
                    'file_size',
                    'datas',
                    'store_fname',
                    'type'
                ]
            }
        )
        
        if not attachment:
            raise HTTPException(
                status_code=404,
                detail=f"No attachment found with ID: {attachment_id}"
            )
            
        attachment = attachment[0]
        print(f"Found attachment: {attachment['name']}")
        
        # Handle both binary and url attachments
        if attachment.get('datas'):
            content = base64.b64decode(attachment['datas'])
            print(f"Retrieved binary content for attachment: {attachment['name']}")
        elif attachment.get('store_fname'):
            # Handle file stored on disk
            content = models.execute_kw(
                db, uid, api_key,
                'ir.attachment', 'get_file',
                [[attachment_id]]
            )
            if not content:
                raise HTTPException(
                    status_code=404,
                    detail=f"Could not retrieve content for attachment: {attachment['name']}"
                )
            print(f"Retrieved file content for attachment: {attachment['name']}")
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No content found for attachment: {attachment['name']}"
            )
            
        # Return the attachment as a streaming response
        return StreamingResponse(
            iter([content]),
            media_type=attachment['mimetype'],
            headers={
                'Content-Disposition': f'attachment; filename="{attachment["name"]}"',
                'Content-Type': attachment['mimetype'],
                'Content-Length': str(len(content))
            }
        )
            
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading attachment: {str(e)}"
        )

def read_attachment_jsonrpc(attachment_id: int):
    """
    Reads an attachment using JSON-RPC endpoint
    """
    try:
        print(f"Reading attachment ID: {attachment_id}")
        
        # Prepare the JSON-RPC request
        jsonrpc_url = f"{url}/jsonrpc"
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    db,
                    uid,
                    api_key,
                    "ir.attachment",
                    "read",
                    [
                        [attachment_id],
                        ["datas", "name", "mimetype"]
                    ]
                ]
            }
        }
        
        print("Sending JSON-RPC request for attachment")
        response = requests.post(jsonrpc_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'result' in result and result['result']:
                attachment = result['result'][0]
                print(f"Successfully read attachment: {attachment['name']}")
                return attachment
            else:
                print(f"Failed to read attachment: {result.get('error', {}).get('message', 'Unknown error')}")
                return None
        else:
            print(f"Failed to read attachment: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error reading attachment: {str(e)}")
        return None

def send_email_with_attachment_jsonrpc(invoice_id: int, template_id: str, attachment_id: int):
    """
    Sends an email with an attachment using JSON-RPC endpoint
    """
    try:
        print(f"Preparing to send email for invoice ID: {invoice_id} with attachment ID: {attachment_id}")
        
        # First read the attachment
        attachment = read_attachment_jsonrpc(attachment_id)
        if not attachment:
            return {
                'success': False,
                'message': 'Failed to read attachment',
                'email_id': None
            }
            
        # Prepare the JSON-RPC request
        jsonrpc_url = f"{url}/jsonrpc"
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Prepare context with attachment
        context = {
            "default_use_template": True,
            "mark_invoice_as_sent": True,
            "custom_layout": "account.mail_template_data_notification_email_account_invoice",
            "force_email": True,
            "attachment_ids": [attachment_id]
        }
        
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    db,
                    uid,
                    api_key,
                    "mail.template",
                    "send_email",
                    [
                        template_id,
                        invoice_id,
                        True
                    ],
                    {
                        "context": context
                    }
                ]
            }
        }
        
        print("Sending email with attachment")
        response = requests.post(jsonrpc_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                print(f"Successfully sent email with attachment")
                return {
                    'success': True,
                    'message': 'Email sent successfully with attachment',
                    'email_id': result['result']
                }
            else:
                print(f"Failed to send email: {result.get('error', {}).get('message', 'Unknown error')}")
                return {
                    'success': False,
                    'message': f"Failed to send email: {result.get('error', {}).get('message', 'Unknown error')}",
                    'email_id': None
                }
        else:
            print(f"Failed to send email: HTTP {response.status_code}")
            return {
                'success': False,
                'message': f"Failed to send email: HTTP {response.status_code}",
                'email_id': None
            }
            
    except Exception as e:
        print(f"Error sending email with attachment: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}",
            'email_id': None
        }

@app.post("/send-invoice-email-with-attachment")
async def send_invoice_email_with_attachment_endpoint(request: EmailRequest):
    """
    Send an email for an invoice with a specific attachment
    """
    try:
        print(f"Received request to send email for invoice ID: {request.invoice_id}")
        
        # Validate invoice exists
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', request.invoice_id], ['company_id', '=', 5]]],
            {'fields': ['name']}
        )
        
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"No invoice found with ID: {request.invoice_id}"
            )
            
        # Validate attachment exists if provided
        if request.attachment_ids and len(request.attachment_ids) > 0:
            attachment_id = request.attachment_ids[0]  # Use first attachment
            result = send_email_with_attachment_jsonrpc(
                request.invoice_id,
                request.template_id,
                attachment_id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="No attachment ID provided"
            )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result['message']
            )
            
        return result
        
    except HTTPException as he:
        print(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending email: {str(e)}"
        )

if __name__ == "__main__":
    try:
        # Try to run on port 8000 first
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except OSError as e:
        if e.errno == 10048:  # Port already in use
            print("Port 8000 is in use, trying port 8001...")
            try:
                uvicorn.run(app, host="0.0.0.0", port=8001)
            except OSError as e:
                if e.errno == 10048:
                    print("Port 8001 is also in use. Please specify a different port or close the application using the current port.")
                    print("You can specify a custom port by running: python run.py --port <port_number>")
                else:
                    print(f"Error starting server: {str(e)}")
        else:
            print(f"Error starting server: {str(e)}")