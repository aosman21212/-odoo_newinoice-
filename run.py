import xmlrpc.client
import requests
import base64
import json
import time
from datetime import datetime, timedelta
import sys
from requests.exceptions import RequestException
from xmlrpc.client import ProtocolError, Fault

# Odoo connection details
url = 'https://odoo-ps-psae-bab-international-corp-staging-21244280.dev.odoo.com'
db = 'odoo-ps-psae-bab-international-corp-staging-21244280'
username = 'admin'
api_key = 'debfa352207d10342eb9900041282b27d914dff8'  # Your API key
pdf_api_key = 'wEUcUsNSIaz8viGwzA_6VnimKdlgbItusDKMGOmVvmZRH33ptRh4MmcIXdujT-zHL8nGypkK8rIqT5TDsKv7'  # PDF API key

def connect_to_odoo(max_retries=3, retry_delay=5):
    """
    Attempts to connect to Odoo with retry logic
    """
    for attempt in range(max_retries):
        try:
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
            uid = common.authenticate(db, username, api_key, {})
            
            if not uid:
                print(f"Authentication failed on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise Exception("Authentication failed after all retries")
                
            print("Successfully connected to Odoo")
            return common, uid
            
        except (ProtocolError, Fault) as e:
            print(f"Connection error on attempt {attempt + 1}/{max_retries}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise

# Initialize connection
try:
    common, uid = connect_to_odoo()
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
except Exception as e:
    print(f"Failed to initialize connection: {str(e)}")
    sys.exit(1)

def validate_invoice_data(invoice):
    """
    Validates invoice data before processing
    """
    required_fields = ['id', 'name', 'state', 'move_type', 'amount_total']
    for field in required_fields:
        if field not in invoice:
            raise ValueError(f"Missing required field: {field}")
    return True

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
                'order': 'create_date asc'
            }
        )
        
        if not invoices:
            print(f"No invoices found for today ({today})")
            return None
            
        # Validate each invoice
        valid_invoices = []
        for inv in invoices:
            try:
                validate_invoice_data(inv)
                valid_invoices.append(inv)
            except ValueError as e:
                print(f"Skipping invalid invoice {inv.get('id', 'unknown')}: {str(e)}")
                continue
            
        if valid_invoices:
            print(f"\nValid invoices for today ({today}):")
            print("------------------------")
            for inv in valid_invoices:
                print(f"ID: {inv['id']} | Name: {inv['name']} | Type: {inv['move_type']} | State: {inv['state']} | Amount: {inv['amount_total']} | Created: {inv['create_date']}")
        
        return valid_invoices
        
    except (Fault, ProtocolError) as e:
        print(f"Odoo API error: {str(e)}")
        return None
    except Exception as e:
        print(f"Error listing today's invoices: {str(e)}")
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
    Gets the PDF URL for an invoice with retry logic
    """
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            pdf_url = f"{url}/report/pdf/studio_customization.studio_report_docume_67b31916-ec11-42bd-8ac0-7dc84926581e/{invoice_id}"
            
            headers = {
                'X-API-Key': pdf_api_key,
                'Cookie': 'frontend_lang=en_US'
            }
            
            session = requests.Session()
            response = session.get(pdf_url, headers=headers, allow_redirects=True, timeout=30)
            
            if response.status_code in [200, 303]:
                final_url = response.url
                print(f"PDF URL (after redirect): {final_url}")
                return final_url
            else:
                print(f"Error verifying PDF URL (attempt {attempt + 1}/{max_retries}): Status code {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
                
        except RequestException as e:
            print(f"Network error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return None
        except Exception as e:
            print(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return None

def show_payload_structure(payload):
    """
    Display the payload structure that will be sent to webhook
    """
    print("\n" + "="*60)
    print("PAYLOAD THAT WILL BE SENT TO WEBHOOK:")
    print("="*60)
    print(json.dumps(payload, indent=2, default=str))
    print("="*60)

def send_invoice_to_webhook(invoice_id):
    """
    Fetches invoice data and creates a comprehensive payload with multiple operations
    """
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # Get all fields from the account.move model for the specific invoice
            invoice = models.execute_kw(
                db, uid, api_key,
                'account.move', 'search_read',
                [[['id', '=', invoice_id], ['company_id', '=', 5]]],
                {
                    'fields': []  # Empty fields list means get all fields
                }
            )
            
            if not invoice:
                print(f"Error: Invoice ID {invoice_id} not found or not accessible for company_id 5")
                return False
                
            invoice_data = invoice[0]
            print(f"Found invoice: {invoice_data['name']} (State: {invoice_data['state']})")

            # Get partner information
            partner_name = "Unknown Partner"
            partner_id = None
            if invoice_data.get('partner_id') and isinstance(invoice_data['partner_id'], list) and len(invoice_data['partner_id']) > 1:
                partner_name = invoice_data['partner_id'][1]
                partner_id = invoice_data['partner_id'][0]

            # Get currency information
            currency = "USD"
            if invoice_data.get('currency_id') and isinstance(invoice_data['currency_id'], list) and len(invoice_data['currency_id']) > 1:
                currency = invoice_data['currency_id'][1]

            # Get invoice lines
            invoice_lines = get_invoice_lines(invoice_id)
            
            # Get partner ledger entries
            ledger_entries = []
            if partner_id:
                ledger_entries = get_partner_ledger_entries(partner_id)
            
            # Get PDF URL
            pdf_url = get_invoice_pdf(invoice_id)

            # Create the comprehensive payload structure
            payload = {
                "model": "new_invoice",
                "id": invoice_id,
                "data": {
                    "operations": [
                        {
                            "name": "fetch_invoice_details",
                            "payload": {
                                "invoice": {
                                    "invoice_name": invoice_data.get('name', ''),
                                    "partner": partner_name,
                                    "invoice_date": invoice_data.get('invoice_date', ''),
                                    "invoice_date_due": invoice_data.get('invoice_date_due', ''),
                                    "amount_total": invoice_data.get('amount_total', 0.0),
                                    "amount_residual": invoice_data.get('amount_residual', 0.0),
                                    "currency": currency,
                                    "invoice_lines": invoice_lines
                                }
                            }
                        },
                        {
                            "name": "partner_ledger",
                            "payload": {
                                "partner_id": partner_id,
                                "partner_name": partner_name,
                                "ledger_entries": ledger_entries
                            }
                        },
                        {
                            "name": "pdf_invoice",
                            "payload": {
                                "invoice_id": invoice_id,
                                "invoice_name": invoice_data.get('name', ''),
                                "pdf_url": pdf_url if pdf_url else ""
                            }
                        }
                    ]
                },
                "company_id": 5
            }

            # Show the payload structure before sending
            show_payload_structure(payload)

            # Webhook URL
            webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent/event'

            # Send the payload to the webhook
            response = requests.post(webhook_url, json=payload, timeout=30)

            if response.status_code == 200:
                print("\nWebhook Response:")
                print("----------------")
                print(f"Status Code: {response.status_code}")
                try:
                    response_json = response.json()
                    print(json.dumps(response_json, indent=2))
                except:
                    print(response.text)
                return True
            else:
                print(f"Webhook error (attempt {attempt + 1}/{max_retries}): Status code {response.status_code}")
                print(f"Response Headers: {dict(response.headers)}")
                print(f"Response Body: {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False

        except (Fault, ProtocolError) as e:
            print(f"Odoo API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
        except RequestException as e:
            print(f"Network error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
        except Exception as e:
            print(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False

# Example usage: Triggered when an invoice is created
def on_invoice_create(invoice_id):
    """
    This function is called when a all invoice is created.
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

def test_webhook_endpoint():
    """
    Test the webhook endpoint with a simple payload to diagnose issues
    """
    print("\nTesting webhook endpoint...")
    print("="*50)
    
    # Test payload with the new structure
    test_payload = {
        "model": "new_invoice",
        "id": 12345,
        "data": {
            "operations": [
                {
                    "name": "fetch_invoice_details",
                    "payload": {
                        "invoice": {
                            "invoice_name": "TEST/2025/001",
                            "partner": "Test Partner",
                            "invoice_date": "2025-01-27",
                            "invoice_date_due": "2025-02-26",
                            "amount_total": 1000.0,
                            "amount_residual": 500.0,
                            "currency": "USD",
                            "invoice_lines": [
                                {
                                    "product": "Test Product A",
                                    "quantity": 2.0,
                                    "price_unit": 250.0,
                                    "subtotal": 500.0
                                },
                                {
                                    "product": "Test Product B",
                                    "quantity": 1.0,
                                    "price_unit": 500.0,
                                    "subtotal": 500.0
                                }
                            ]
                        }
                    }
                },
                {
                    "name": "partner_ledger",
                    "payload": {
                        "partner_id": 101,
                        "partner_name": "Test Partner",
                        "ledger_entries": [
                            {
                                "id": 1001,
                                "date": "2025-01-27",
                                "name": "Invoice TEST/2025/001",
                                "debit": 1000.0,
                                "credit": 0.0,
                                "balance": 1000.0
                            },
                            {
                                "id": 1002,
                                "date": "2025-01-30",
                                "name": "Payment for TEST/2025/001",
                                "debit": 0.0,
                                "credit": 500.0,
                                "balance": 500.0
                            }
                        ]
                    }
                },
                {
                    "name": "pdf_invoice",
                    "payload": {
                        "invoice_id": 12345,
                        "invoice_name": "TEST/2025/001",
                        "pdf_url": "https://example.com/invoices/TEST-2025-001.pdf"
                    }
                }
            ]
        },
        "company_id": 5
    }
    
    webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent/event'
    
    try:
        print(f"Sending test payload to: {webhook_url}")
        print("Test Payload:")
        print(json.dumps(test_payload, indent=2))
        
        response = requests.post(webhook_url, json=test_payload, timeout=30)
        
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✓ Webhook test successful!")
            return True
        else:
            print("✗ Webhook test failed!")
            return False
            
    except Exception as e:
        print(f"✗ Webhook test error: {str(e)}")
        return False

def get_invoice_lines(invoice_id):
    """
    Gets the invoice lines for a specific invoice
    """
    try:
        # Search for invoice lines for the invoice
        invoice_lines = models.execute_kw(
            db, uid, api_key,
            'account.move.line', 'search_read',
            [[
                ['move_id', '=', invoice_id],
                ['company_id', '=', 5],
                ['exclude_from_invoice_tab', '=', False]  # Only invoice lines, not payment lines
            ]],
            {
                'fields': [
                    'id',
                    'name',
                    'quantity',
                    'price_unit',
                    'price_subtotal',
                    'product_id',
                    'account_id'
                ],
                'order': 'sequence asc'
            }
        )
        
        if not invoice_lines:
            print(f"No invoice lines found for invoice ID {invoice_id}")
            return []
        
        # Format invoice lines
        formatted_lines = []
        for line in invoice_lines:
            product_name = "Unknown Product"
            if line.get('product_id') and isinstance(line['product_id'], list) and len(line['product_id']) > 1:
                product_name = line['product_id'][1]
            
            formatted_lines.append({
                "product": product_name,
                "quantity": line.get('quantity', 0.0),
                "price_unit": line.get('price_unit', 0.0),
                "subtotal": line.get('price_subtotal', 0.0)
            })
        
        return formatted_lines
        
    except Exception as e:
        print(f"Error getting invoice lines: {str(e)}")
        return []

def get_invoice_attachments(invoice_id):
    """
    Gets the attachments for a specific invoice
    """
    try:
        # Search for attachments related to the invoice
        attachments = models.execute_kw(
            db, uid, api_key,
            'ir.attachment', 'search_read',
            [[
                ['res_model', '=', 'account.move'],
                ['res_id', '=', invoice_id],
                ['company_id', '=', 5]
            ]],
            {
                'fields': [
                    'id',
                    'name',
                    'mimetype',
                    'file_size',
                    'create_date',
                    'write_date',
                    'type'
                ]
            }
        )
        
        if not attachments:
            print(f"No attachments found for invoice ID {invoice_id}")
            return []
        
        # Format attachments
        formatted_attachments = []
        for attachment in attachments:
            # Generate URL for the attachment
            attachment_url = f"{url}/web/content/{attachment['id']}?download=true"
            
            formatted_attachments.append({
                "id": attachment['id'],
                "name": attachment.get('name', 'Unknown'),
                "mimetype": attachment.get('mimetype', 'application/octet-stream'),
                "file_size": attachment.get('file_size', 0),
                "create_date": attachment.get('create_date', ''),
                "write_date": attachment.get('write_date', ''),
                "type": attachment.get('type', 'attachment'),
                "url": attachment_url
            })
        
        return formatted_attachments
        
    except Exception as e:
        print(f"Error getting invoice attachments: {str(e)}")
        return []

def get_partner_ledger_entries(partner_id):
    """
    Gets the ledger entries for a specific partner
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
                'order': 'date asc'
            }
        )
        
        if not ledger_entries:
            print(f"No ledger entries found for partner ID {partner_id}")
            return []
        
        # Format ledger entries
        formatted_entries = []
        for entry in ledger_entries:
            formatted_entries.append({
                "id": entry['id'],
                "date": entry.get('date', ''),
                "name": entry.get('name', ''),
                "debit": entry.get('debit', 0.0),
                "credit": entry.get('credit', 0.0),
                "balance": entry.get('balance', 0.0)
            })
        
        return formatted_entries
        
    except Exception as e:
        print(f"Error getting partner ledger entries: {str(e)}")
        return []

if __name__ == "__main__":
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    # Test webhook endpoint first
    print("Testing webhook endpoint before processing invoices...")
    webhook_test_result = test_webhook_endpoint()
    
    if not webhook_test_result:
        print("\nWarning: Webhook test failed. The endpoint may have issues.")
        print("Do you want to continue with invoice processing? (y/n): ", end="")
        user_input = input().strip().lower()
        if user_input != 'y':
            print("Exiting due to webhook test failure.")
            sys.exit(1)
    
    while True:
        try:
            print("\nChecking for today's invoices...")
            invoices = get_todays_invoices()
            
            if invoices:
                print(f"\nFound {len(invoices)} invoices for today")
                
                # Process each invoice one by one
                for invoice in invoices:
                    print(f"\nProcessing invoice: {invoice['name']}")
                    if process_invoice(invoice['id']):
                        print(f"Successfully processed invoice: {invoice['name']}")
                        consecutive_errors = 0  # Reset error counter on success
                    else:
                        print(f"Failed to process invoice: {invoice['name']}")
                        consecutive_errors += 1
                    
                    # Wait 5 seconds between processing each invoice
                    time.sleep(5)
                
                print("\nFinished processing all invoices for today")
            else:
                print("No invoices to process")
                consecutive_errors = 0  # Reset error counter when no invoices found
            
            # Check if we've hit the maximum consecutive errors
            if consecutive_errors >= max_consecutive_errors:
                print(f"\nToo many consecutive errors ({consecutive_errors}). Attempting to reconnect...")
                try:
                    common, uid = connect_to_odoo()
                    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
                    consecutive_errors = 0
                    print("Successfully reconnected")
                except Exception as e:
                    print(f"Failed to reconnect: {str(e)}")
                    print("Waiting 5 minutes before retrying...")
                    time.sleep(300)
                    continue
            
            # Wait for 1 minute before next check
            print("\nWaiting 1 minute before next check...")
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\nScript stopped by user")
            break
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            consecutive_errors += 1
            print("Retrying in 5 seconds...")
            time.sleep(5)