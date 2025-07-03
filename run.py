import xmlrpc.client
import requests
import time
import json
from datetime import datetime, timedelta
import sys
from requests.exceptions import RequestException
from xmlrpc.client import ProtocolError, Fault

# Odoo connection details
url = 'https://odoo-ps-psae-bab-international-corp-staging-21688559.dev.odoo.com/'
db = 'odoo-ps-psae-bab-international-corp-staging-21688559'
username = 'admin'
api_key = '0bfbd12888c5656b0ba6a463cb9ed776ab5661f9'  # Your API key

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

def get_todays_records(model_name, domain, fields):
    """
    Fetches records created today for the given model and domain
    """
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        records = models.execute_kw(
            db, uid, api_key,
            model_name, 'search_read',
            [[*domain, ['create_date', '>=', today], ['create_date', '<', tomorrow]]],
            {'fields': fields, 'order': 'create_date asc'}
        )
        
        # If we have partner_id field, fetch partner details
        if records and 'partner_id' in fields:
            partner_ids = [record['partner_id'][0] for record in records if record.get('partner_id')]
            if partner_ids:
                partner_details = models.execute_kw(
                    db, uid, api_key,
                    'res.partner', 'read',
                    [partner_ids],
                    {'fields': ['name', 'email', 'phone', 'street', 'city', 'country_id', 'vat']}
                )
                partner_dict = {partner['id']: partner for partner in partner_details}
                
                # Add partner details to records
                for record in records:
                    if record.get('partner_id'):
                        partner_id = record['partner_id'][0]
                        if partner_id in partner_dict:
                            record['partner_name'] = partner_dict[partner_id]['name']
                            record['partner_email'] = partner_dict[partner_id]['email']
                            record['partner_phone'] = partner_dict[partner_id].get('phone', '')
                            record['partner_address'] = partner_dict[partner_id].get('street', '')
                            record['partner_city'] = partner_dict[partner_id].get('city', '')
                            record['partner_vat'] = partner_dict[partner_id].get('vat', '')
                        else:
                            record['partner_name'] = 'Unknown'
                            record['partner_email'] = ''
                            record['partner_phone'] = ''
                            record['partner_address'] = ''
                            record['partner_city'] = ''
                            record['partner_vat'] = ''
                    else:
                        record['partner_name'] = 'Unknown'
                        record['partner_email'] = ''
                        record['partner_phone'] = ''
                        record['partner_address'] = ''
                        record['partner_city'] = ''
                        record['partner_vat'] = ''
        
        # Fetch invoice line details if invoice_line_ids is present
        if records and 'invoice_line_ids' in fields:
            for record in records:
                if record.get('invoice_line_ids'):
                    line_ids = record['invoice_line_ids']
                    if line_ids:
                        line_details = models.execute_kw(
                            db, uid, api_key,
                            'account.move.line', 'read',
                            [line_ids],
                            {'fields': ['name', 'quantity', 'price_unit', 'price_subtotal', 'price_total', 
                                       'product_id', 'account_id', 'tax_ids', 'discount']}
                        )
                        record['invoice_lines'] = line_details
                    else:
                        record['invoice_lines'] = []
                else:
                    record['invoice_lines'] = []
        
        # Fetch payment method details if payment_method_id is present
        if records and 'payment_method_id' in fields:
            payment_method_ids = [record['payment_method_id'][0] for record in records if record.get('payment_method_id')]
            if payment_method_ids:
                payment_method_details = models.execute_kw(
                    db, uid, api_key,
                    'account.payment.method', 'read',
                    [payment_method_ids],
                    {'fields': ['name', 'code']}
                )
                payment_method_dict = {pm['id']: pm for pm in payment_method_details}
                
                for record in records:
                    if record.get('payment_method_id'):
                        pm_id = record['payment_method_id'][0]
                        if pm_id in payment_method_dict:
                            record['payment_method_name'] = payment_method_dict[pm_id]['name']
                            record['payment_method_code'] = payment_method_dict[pm_id]['code']
                        else:
                            record['payment_method_name'] = 'Unknown'
                            record['payment_method_code'] = ''
                    else:
                        record['payment_method_name'] = ''
                        record['payment_method_code'] = ''
        
        # Fetch journal details if journal_id is present
        if records and 'journal_id' in fields:
            journal_ids = [record['journal_id'][0] for record in records if record.get('journal_id')]
            if journal_ids:
                journal_details = models.execute_kw(
                    db, uid, api_key,
                    'account.journal', 'read',
                    [journal_ids],
                    {'fields': ['name', 'code', 'type']}
                )
                journal_dict = {journal['id']: journal for journal in journal_details}
                
                for record in records:
                    if record.get('journal_id'):
                        journal_id = record['journal_id'][0]
                        if journal_id in journal_dict:
                            record['journal_name'] = journal_dict[journal_id]['name']
                            record['journal_code'] = journal_dict[journal_id]['code']
                            record['journal_type'] = journal_dict[journal_id]['type']
                        else:
                            record['journal_name'] = 'Unknown'
                            record['journal_code'] = ''
                            record['journal_type'] = ''
                    else:
                        record['journal_name'] = ''
                        record['journal_code'] = ''
                        record['journal_type'] = ''
        
        # Fetch currency details if currency_id is present
        if records and 'currency_id' in fields:
            currency_ids = [record['currency_id'][0] for record in records if record.get('currency_id')]
            if currency_ids:
                currency_details = models.execute_kw(
                    db, uid, api_key,
                    'res.currency', 'read',
                    [currency_ids],
                    {'fields': ['name', 'symbol', 'position']}
                )
                currency_dict = {currency['id']: currency for currency in currency_details}
                
                for record in records:
                    if record.get('currency_id'):
                        currency_id = record['currency_id'][0]
                        if currency_id in currency_dict:
                            record['currency_name'] = currency_dict[currency_id]['name']
                            record['currency_symbol'] = currency_dict[currency_id]['symbol']
                            record['currency_position'] = currency_dict[currency_id]['position']
                        else:
                            record['currency_name'] = 'Unknown'
                            record['currency_symbol'] = ''
                            record['currency_position'] = ''
                    else:
                        record['currency_name'] = ''
                        record['currency_symbol'] = ''
                        record['currency_position'] = ''
        
        return records or []
    except Exception as e:
        print(f"Error fetching records: {str(e)}")
        return []

def prepare_payload(model_name, record):
    """
    Prepares the payload for sending to the webhook
    """
    payload = {
        "model": model_name,
        "data": record
    }
    return payload

def send_to_webhook(payload):
    """
    Sends the payload to the webhook
    """
    webhook_url = 'https://odoo-agent-main-113251955071.me-central1.run.app/agent/event'
    try:
        print(f"Sending payload to webhook: {webhook_url}")
        print(f"Payload size: {len(str(payload))} characters")
        
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"Webhook response status: {response.status_code}")
        
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
            print(f"Webhook error: Status code {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Body: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("Webhook request timed out after 30 seconds")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error to webhook: {str(e)}")
        return False
    except Exception as e:
        print(f"Error sending to webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def process_records(model_name, domain, fields, record_type):
    """
    Fetches and processes records of a specific type
    """
    try:
        records = get_todays_records(model_name, domain, fields)
        if not records:
            print(f"No {record_type} found for today")
            return
        print(f"\nFound {len(records)} {record_type}(s) for today")
        for record in records:
            try:
                print(f"\nProcessing {record_type}: {record.get('name', 'N/A')}")
                print(f"Record ID: {record.get('id', 'N/A')}")
                print(f"Partner: {record.get('partner_name', 'N/A')}")
                print(f"Amount: {record.get('amount_total', 'N/A')}")
                
                payload = prepare_payload(model_name, record)
                print(f"Payload prepared successfully")
                
                if send_to_webhook(payload):
                    print(f"Successfully processed {record_type}: {record.get('name', 'N/A')}")
                else:
                    print(f"Failed to process {record_type}: {record.get('name', 'N/A')}")
            except Exception as e:
                print(f"Error processing individual {record_type} {record.get('name', 'N/A')}: {str(e)}")
                print(f"Record data: {record}")
                continue
    except Exception as e:
        print(f"Error in process_records for {record_type}: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    while True:
        try:
            print("\nFetching customer invoices...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'out_invoice']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'amount_untaxed', 'amount_tax', 
                 'partner_id', 'invoice_date', 'invoice_date_due', 'payment_reference', 'ref', 
                 'currency_id', 'payment_state', 'invoice_line_ids', 'narration'],
                'Customer Invoice'
            )

            print("\nFetching customer credit notes...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'out_refund']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'amount_untaxed', 'amount_tax', 
                 'partner_id', 'invoice_date', 'invoice_date_due', 'payment_reference', 'ref', 
                 'currency_id', 'payment_state', 'invoice_line_ids', 'narration'],
                'Customer Credit Note'
            )

            print("\nFetching customer payments...")
            process_records(
                'account.payment',
                [['company_id', '=', 5], ['payment_type', '=', 'inbound']],
                ['id', 'name', 'state', 'payment_type', 'amount', 'partner_id', 'date', 
                 'payment_method_id', 'journal_id', 'currency_id', 'ref', 'narration'],
                'Customer Payment'
            )

            print("\nFetching vendor invoices...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'in_invoice']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'amount_untaxed', 'amount_tax', 
                 'partner_id', 'invoice_date', 'invoice_date_due', 'payment_reference', 'ref', 
                 'currency_id', 'payment_state', 'invoice_line_ids', 'narration'],
                'Vendor Invoice'
            )

            print("\nFetching vendor refunds...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'in_refund']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'amount_untaxed', 'amount_tax', 
                 'partner_id', 'invoice_date', 'invoice_date_due', 'payment_reference', 'ref', 
                 'currency_id', 'payment_state', 'invoice_line_ids', 'narration'],
                'Vendor Refund'
            )

            print("\nFetching vendor payments...")
            process_records(
                'account.payment',
                [['company_id', '=', 5], ['payment_type', '=', 'outbound']],
                ['id', 'name', 'state', 'payment_type', 'amount', 'partner_id', 'date', 
                 'payment_method_id', 'journal_id', 'currency_id', 'ref', 'narration'],
                'Vendor Payment'
            )

            print("\nWaiting 1 minute before next check...")
            time.sleep(60)

        except KeyboardInterrupt:
            print("\nScript stopped by user")
            break
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()