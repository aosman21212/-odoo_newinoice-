import xmlrpc.client
import requests
import base64
import json
import time
from datetime import datetime, timedelta

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
    Gets the PDF URL for an invoice
    """
    try:
        # Construct the PDF URL
        pdf_url = f"{url}/report/pdf/studio_customization.studio_report_docume_67b31916-ec11-42bd-8ac0-7dc84926581e/{invoice_id}"
        
        # Set up headers with API key
        headers = {
            'X-API-Key': pdf_api_key,
            'Cookie': 'frontend_lang=en_US'
        }
        
        # Get the PDF URL with redirect following
        session = requests.Session()
        response = session.get(pdf_url, headers=headers, allow_redirects=True)
        
        if response.status_code in [200, 303]:
            # Get the final URL after redirects
            final_url = response.url
            print(f"PDF URL (after redirect): {final_url}")
            return final_url
        else:
            print(f"Error verifying PDF URL: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error getting PDF URL: {str(e)}")
        return None

def send_invoice_to_webhook(invoice_id):
    """
    Fetches the PDF URL of the given invoice and sends it to the webhook.
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
                    "move_type"
                ]
            }
        )
        
        if not invoice:
            print(f"Error: Invoice ID {invoice_id} not found or not accessible for company_id 5")
            return
            
        print(f"Found invoice: {invoice[0]['name']} (State: {invoice[0]['state']})")

        # Get the PDF URL
        pdf_url = get_invoice_pdf(invoice_id)
        if not pdf_url:
            print("Failed to get PDF URL")
            return

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

        # Prepare the payload with all invoice information
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
                            } for line in invoice_lines]
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
        print(f"\nPDF URL: {pdf_url}")
        print(f"\nNumber of Partner Ledger Entries: {len(partner_ledger) if partner_ledger else 0}")

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

if __name__ == "__main__":
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
                    else:
                        print(f"Failed to process invoice: {invoice['name']}")
                    
                    # Wait 5 seconds between processing each invoice
                    time.sleep(5)
                
                print("\nFinished processing all invoices for today")
            else:
                print("No invoices to process")
            
            # Wait for 5 minutes before next check
            print("\nWaiting 5 minutes before next check...")
            time.sleep(300)  # 300 seconds = 5 minutes
            
        except KeyboardInterrupt:
            print("\nScript stopped by user")
            break
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            print("Retrying in 5 seconds...")
            time.sleep(5)