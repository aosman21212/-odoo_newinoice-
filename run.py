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
api_key = '665226cf06269d4a9402d41475b3b052b8980644'  # Your API key
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

def send_invoice_to_webhook(invoice_id):
    """
    Fetches the PDF URL of the given invoice and sends it to the webhook with retry logic
    """
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # Verify invoice exists and is accessible
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
                        "user_id",
                        "move_type",
                        "attachment_ids"
                    ]
                }
            )
            
            if not invoice:
                print(f"Error: Invoice ID {invoice_id} not found or not accessible for company_id 5")
                return False
                
            print(f"Found invoice: {invoice[0]['name']} (State: {invoice[0]['state']})")

            # Get the PDF URL
            pdf_url = get_invoice_pdf(invoice_id)
            if not pdf_url:
                print("Failed to get PDF URL")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False

            # Get partner details
            partner = models.execute_kw(
                db, uid, api_key,
                'res.partner', 'search_read',
                [[['id', '=', invoice[0]['partner_id'][0]]]],
                {'fields': ['name', 'email', 'phone', 'street', 'city', 'country_id']}
            )

            # Get partner ledger entries
            partner_ledger = get_partner_ledger(invoice[0]['partner_id'][0])

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

            # Get attachments
            attachments = []
            if invoice[0].get('attachment_ids'):
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
                            'write_date',
                            'type',
                            'url'
                        ]
                    }
                )

            # Prepare the payload
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
                                "amount_residual": invoice[0]['amount_residual'],
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
                                    "url": att['url']
                                } for att in attachments]
                            },
                            "company_id": 5
                        }
                    },
                    {
                        "name": "payment_reminder",
                        "payload": {
                            "invoice": {
                                "invoice_name": invoice[0]['name'],
                                "partner": partner[0]['name'] if partner else "",
                                "amount_residual": invoice[0]['amount_residual'],
                                "currency": invoice_lines[0]['currency_id'][1] if invoice_lines and invoice_lines[0]['currency_id'] else "",
                                "invoice_date_due": invoice[0]['invoice_date_due']
                            },
                            "company_id": 5
                        }
                    },
                    {
                        "name": "partner_ledger",
                        "payload": {
                            "partner_id": invoice[0]['partner_id'][0],
                            "partner_name": partner[0]['name'] if partner else "",
                            "ledger_entries": partner_ledger if partner_ledger else [],
                            "company_id": 5
                        }
                    },
                    {
                        "name": "pdf_invoice",
                        "payload": {
                            "invoice_id": invoice[0]['id'],
                            "invoice_name": invoice[0]['name'],
                            "pdf_url": pdf_url,
                            "company_id": 5
                        }
                    }
                ]
            }

            # Webhook URL
            webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent'

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

if __name__ == "__main__":
    consecutive_errors = 0
    max_consecutive_errors = 5
    
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