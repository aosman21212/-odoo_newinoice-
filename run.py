import xmlrpc.client
import requests
import base64
import json
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
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
api_key = '2558e476e9e29ee4588ae214fb27354c72bdf03e'  # Your API key
pdf_api_key = 'wEUcUsNSIaz8viGwzA_6VnimKdlgbItusDKMGOmVvmZRH33ptRh4MmcIXdujT-zHL8nGypkK8rIqT5TDsKv7'  # PDF API key

# Authenticate with Odoo
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, api_key, {})

if not uid:
    print("Authentication failed. Please check your credentials.")
    exit(1)

# Initialize the models endpoint
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

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
    email_cc: Optional[str] = None
    email_bcc: Optional[str] = None
    reply_to: Optional[str] = None
    auto_delete: bool = True
    user_signature: bool = True

class EmailTemplateResponse(BaseModel):
    success: bool
    message: str
    template_id: Optional[int] = None

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

def get_invoice_pdf(invoice_id):
    """
    Gets the PDF content for an invoice
    """
    try:
        # Construct the PDF URL
        pdf_url = f"{url}/report/pdf/studio_customization.studio_report_docume_67b31916-ec11-42bd-8ac0-7dc84926581e/{invoice_id}"
        
        # Set up headers with API key
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Get the PDF content with redirect following
        session = requests.Session()
        response = session.get(pdf_url, headers=headers, allow_redirects=True)
        
        if response.status_code in [200, 303]:
            # Get the PDF content
            pdf_content = response.content
            print(f"Successfully retrieved PDF content ({len(pdf_content)} bytes)")
            
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
    Fetches the PDF content of the given invoice and sends it to the webhook.
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
                    "invoice_line_ids",
                    "state",
                    "user_id",
                    "move_type",
                    "attachment_ids"
                ]
            }
        )
        
        if not invoice:
            print(f"Error: Invoice ID {invoice_id} not found or not accessible for company_id 5")
            return
            
        print(f"Found invoice: {invoice[0]['name']} (State: {invoice[0]['state']})")

        # Get the PDF content
        pdf_content = get_invoice_pdf(invoice_id)
        if not pdf_content:
            print("Failed to get PDF content")
            return

        # Get partner details
        partner = models.execute_kw(
            db, uid, api_key,
            'res.partner', 'search_read',
            [[['id', '=', invoice[0]['partner_id'][0]]]],
            {'fields': ['name', 'email', 'phone', 'street', 'city', 'country_id']}
        )

        # Get invoice line details
        invoice_lines = models.execute_kw(
            db, uid, api_key,
            'account.move.line', 'search_read',
            [[['id', 'in', invoice[0]['invoice_line_ids']]]],
            {
                'fields': [
                    'name',
                    'quantity',
                    'price_unit',
                    'price_subtotal',
                    'price_total',
                    'product_id',
                    'tax_ids',
                    'discount',
                    'currency_id',
                    'account_id',
                    'company_id',
                    'date',
                    'debit',
                    'credit',
                    'balance',
                    'amount_currency',
                    'move_id'
                ]
            }
        )

        # Get attachment details
        attachments = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[['id', 'in', invoice[0]['attachment_ids']]]],
            {
                'fields': [
                    'id',
                    'name',
                    'mimetype',
                    'file_size',
                    'create_date',
                    'write_date'
                ]
            }
        ) if invoice[0]['attachment_ids'] else []

        # Prepare the payload with only fetch_invoice_details and pdf_invoice operations
        payload = {
            "event": "new_invoice",
            "operations": [
                {
                    "name": "fetch_invoice_details",
                    "payload": {
                        "invoice": {
                            "invoice_name": invoice[0]['name'],
                            "partner": partner[0]['name'] if partner else "",
                            "invoice_date": invoice[0]['invoice_date'],
                            "invoice_date_due": invoice[0]['invoice_date_due'],
                            "amount_total": invoice[0]['amount_total'],
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
                                "write_date": att['write_date']
                            } for att in attachments]
                        },
                        "company_id": 5
                    }
                },
                {
                    "name": "pdf_invoice",
                    "payload": {
                        "invoice_id": invoice[0]['id'],
                        "invoice_name": invoice[0]['name'],
                        "pdf_content": pdf_content,
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

        # Print a summary of the sent invoice
        print("\nSent Invoice Summary:")
        print("-------------------")
        print(f"Invoice ID: {invoice[0]['id']}")
        print(f"Invoice Name: {invoice[0]['name']}")
        print(f"Total Amount: {invoice[0]['amount_total']}")
        print(f"Number of Lines: {len(invoice_lines)}")
        print(f"Partner: {partner[0]['name'] if partner else 'N/A'}")
        print(f"State: {invoice[0]['state']}")
        print(f"Type: {invoice[0]['move_type']}")
        print(f"\nPDF Content Size: {len(pdf_content)} bytes")

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
    except Exception as e:
        print("Error sending invoice to webhook:", str(e))

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
            
        # Print the raw JSON response
        print("\nRaw JSON Response:")
        print("-----------------")
        print(json.dumps({
            "jsonrpc": "2.0",
            "result": ledger_entries
        }, indent=2))
        
        print("\nPartner Ledger Entries:")
        print("----------------------")
        for entry in ledger_entries:
            print(f"Date: {entry['date']} | Name: {entry['name']} | Debit: {entry['debit']} | Credit: {entry['credit']} | Balance: {entry['balance']}")
        
        return ledger_entries
        
    except Exception as e:
        print("Error getting partner ledger:", str(e))
        return None

@app.get("/invoice-attachments/{invoice_id}")
async def get_invoice_attachments(invoice_id: int):
    """
    Get all attachments for a specific invoice
    """
    try:
        # Get invoice with attachments
        invoice = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice_id], ['company_id', '=', 5]]],
            {
                'fields': [
                    'name',
                    'attachment_ids'
                ]
            }
        )
        
        if not invoice:
            raise HTTPException(status_code=404, detail=f"No invoice found with ID: {invoice_id}")
            
        invoice = invoice[0]
        
        # Get attachment details
        attachments = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[['id', 'in', invoice['attachment_ids']]]],
            {
                'fields': [
                    'id',
                    'name',
                    'mimetype',
                    'file_size',
                    'create_date',
                    'write_date'
                ]
            }
        ) if invoice['attachment_ids'] else []
        
        return {
            "invoice_name": invoice['name'],
            "attachments": attachments
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint to check if API is running"""
    return {"message": "Invoice Processing API is running"}

@app.post("/process-invoice", response_model=InvoiceResponse)
async def process_invoice_endpoint(request: InvoiceRequest):
    """
    Process an invoice by its invoice number
    """
    try:
        # Get the invoice
        invoice = get_invoice_by_number(request.invoice_number)
        
        if not invoice:
            raise HTTPException(status_code=404, detail=f"No invoice found with number: {request.invoice_number}")
        
        # Process the invoice
        success = process_invoice(invoice['id'])
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to process invoice: {invoice['name']}")
        
        # Get invoice details for response
        invoice_details = models.execute_kw(
            db, uid, api_key,
            'account.move', 'search_read',
            [[['id', '=', invoice['id']]]],
            {
                'fields': [
                    "name",
                    "partner_id",
                    "invoice_date",
                    "invoice_date_due",
                    "amount_total",
                    "invoice_line_ids",
                    "state",
                    "move_type",
                    "attachment_ids"
                ]
            }
        )[0]

        # Get attachment details
        attachments = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[['id', 'in', invoice_details['attachment_ids']]]],
            {
                'fields': [
                    'id',
                    'name',
                    'mimetype',
                    'file_size',
                    'create_date',
                    'write_date'
                ]
            }
        ) if invoice_details['attachment_ids'] else []

        # Get partner details
        partner = models.execute_kw(
            db, uid, api_key,
            'res.partner', 'search_read',
            [[['id', '=', invoice_details['partner_id'][0]]]],
            {'fields': ['name']}
        )[0]
        
        # Get invoice lines
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
        
        # Get partner ledger
        partner_ledger = get_partner_ledger(invoice_details['partner_id'][0])
        
        # Get PDF content
        pdf_content = get_invoice_pdf(invoice['id'])

        # Send email with attachments
        try:
            # Get template ID
            template = models.execute_kw(
                db, uid, api_key,
                'mail.template', 'search_read',
                [[['name', '=', "Invoice: Send by email"]]],
                {'fields': ['id']}
            )
            
            if template:
                template_id = template[0]['id']
                
                # Prepare context for email
                context = {
                    "default_use_template": True,
                    "mark_invoice_as_sent": True,
                    "custom_layout": "account.mail_template_data_notification_email_account_invoice",
                    "force_email": True
                }
                
                # Add attachment IDs if any exist
                if attachments:
                    context["attachment_ids"] = [att['id'] for att in attachments]
                
                # Send email using template
                email_result = models.execute_kw(
                    db, uid, api_key,
                    'mail.template', 'send_mail',
                    [template_id, invoice['id'], True],
                    {
                        'context': context
                    }
                )
                
                print(f"Email sent successfully for invoice {invoice['name']}")
            else:
                print(f"Warning: Email template not found for invoice {invoice['name']}")
            
        except Exception as e:
            print(f"Warning: Failed to send email for invoice {invoice['name']}: {str(e)}")
            # Continue processing even if email fails
        
        # Prepare response
        response = InvoiceResponse(
            success=True,
            message=f"Successfully processed invoice: {invoice['name']}",
            invoice_details=InvoiceDetails(
                invoice_name=invoice_details['name'],
                partner=partner['name'],
                invoice_date=invoice_details['invoice_date'],
                invoice_date_due=invoice_details['invoice_date_due'],
                amount_total=invoice_details['amount_total'],
                currency=invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                invoice_lines=[
                    InvoiceLine(
                        product=line['product_id'][1] if line['product_id'] else "",
                        quantity=line['quantity'],
                        price_unit=line['price_unit'],
                        subtotal=line['price_subtotal']
                    ) for line in invoice_lines
                ],
                attachment_ids=[{
                    "id": att['id'],
                    "name": att['name'],
                    "mimetype": att['mimetype'],
                    "file_size": att['file_size'],
                    "create_date": att['create_date'],
                    "write_date": att['write_date']
                } for att in attachments]
            ),
            partner_ledger=PartnerLedger(
                partner_id=invoice_details['partner_id'][0],
                partner_name=partner['name'],
                ledger_entries=[
                    PartnerLedgerEntry(
                        date=entry['date'],
                        name=entry['name'],
                        debit=entry['debit'],
                        credit=entry['credit'],
                        balance=entry['balance']
                    ) for entry in partner_ledger
                ] if partner_ledger else []
            ),
            pdf_invoice=PDFInvoice(
                invoice_id=invoice['id'],
                invoice_name=invoice['name'],
                pdf_content=pdf_content
            ) if pdf_content else None
        )
        
        return response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Create template
        template_id = models.execute_kw(
            db, uid, api_key,
            'mail.template', 'create',
            [{
                'name': template_data.name,
                'model_id': model_id,
                'subject': template_data.subject,
                'body_html': template_data.body_html,
                'email_from': template_data.email_from,
                'email_to': template_data.email_to,
                'email_cc': template_data.email_cc,
                'email_bcc': template_data.email_bcc,
                'reply_to': template_data.reply_to,
                'auto_delete': template_data.auto_delete,
                'user_signature': template_data.user_signature
            }]
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