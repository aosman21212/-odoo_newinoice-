import xmlrpc.client
import requests
import time
import json
from datetime import datetime, timedelta
import sys
from requests.exceptions import RequestException
from xmlrpc.client import ProtocolError, Fault

# Odoo connection details
url = 'https://odoo-ps-psae-bab-international-corp-staging-21244280.dev.odoo.com'
db = 'odoo-ps-psae-bab-international-corp-staging-21244280'
username = 'admin'
api_key = 'debfa352207d10342eb9900041282b27d914dff8'  # Your API key

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
            print(f"Webhook error: Status code {response.status_code}")
            print(f"Response Body: {response.text}")
            return False
    except Exception as e:
        print(f"Error sending to webhook: {str(e)}")
        return False

def process_records(model_name, domain, fields, record_type):
    """
    Fetches and processes records of a specific type
    """
    records = get_todays_records(model_name, domain, fields)
    if not records:
        print(f"No {record_type} found for today")
        return
    print(f"\nFound {len(records)} {record_type}(s) for today")
    for record in records:
        print(f"\nProcessing {record_type}: {record.get('name', 'N/A')}")
        payload = prepare_payload(model_name, record)
        if send_to_webhook(payload):
            print(f"Successfully processed {record_type}: {record.get('name', 'N/A')}")
        else:
            print(f"Failed to process {record_type}: {record.get('name', 'N/A')}")

def main():
    while True:
        try:
            print("\nFetching customer invoices...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'out_invoice']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'partner_id'],
                'Customer Invoice'
            )

            print("\nFetching customer credit notes...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'out_refund']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'partner_id'],
                'Customer Credit Note'
            )

            print("\nFetching customer payments...")
            process_records(
                'account.payment',
                [['company_id', '=', 5], ['payment_type', '=', 'inbound']],
                ['id', 'name', 'state', 'payment_type', 'amount', 'partner_id'],
                'Customer Payment'
            )

            print("\nFetching vendor invoices...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'in_invoice']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'partner_id'],
                'Vendor Invoice'
            )

            print("\nFetching vendor refunds...")
            process_records(
                'account.move',
                [['company_id', '=', 5], ['move_type', '=', 'in_refund']],
                ['id', 'name', 'state', 'move_type', 'amount_total', 'partner_id'],
                'Vendor Refund'
            )

            print("\nFetching vendor payments...")
            process_records(
                'account.payment',
                [['company_id', '=', 5], ['payment_type', '=', 'outbound']],
                ['id', 'name', 'state', 'payment_type', 'amount', 'partner_id'],
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