# Odoo Invoice Processing Script

## Overview
This script automates the process of monitoring and processing invoices in an Odoo system. It checks for new invoices every minute, processes them, and sends the data to a webhook endpoint.

## Features
- Automatic invoice monitoring
- PDF generation and processing
- Partner ledger integration
- Webhook integration
- Attachment handling
- Payment reminder processing
- Robust error handling and retry mechanisms
- Automatic reconnection on failures

## Prerequisites
- Python 3.6 or higher
- Required Python packages:
  - xmlrpc.client
  - requests
  - base64
  - json
  - datetime

## Configuration
The script requires the following configuration parameters:

```python
# Odoo connection details
url = 'your-odoo-url'
db = 'your-database-name'
username = 'your-username'
api_key = 'your-api-key'
pdf_api_key = 'your-pdf-api-key'
```

## Installation
1. Clone the repository
2. Install required packages:
```bash
pip install requests
```

## Usage
Run the script using:
```bash
python run.py
```

## Main Functions

### connect_to_odoo(max_retries=3, retry_delay=5)
Establishes connection with Odoo server.
- Parameters:
  - max_retries: Maximum number of connection attempts (default: 3)
  - retry_delay: Delay between retries in seconds (default: 5)
- Returns: tuple (common, uid) containing connection objects

### get_todays_invoices()
Retrieves all invoices created today for company_id 5.
- Returns: List of invoice dictionaries or None if no invoices found

### process_invoice(invoice_id)
Processes a single invoice by sending it to the webhook.
- Parameters:
  - invoice_id: ID of the invoice to process
- Returns: Boolean indicating success/failure

### get_invoice_pdf(invoice_id)
Retrieves the PDF URL for an invoice.
- Parameters:
  - invoice_id: ID of the invoice
- Returns: PDF URL string or None if failed

### send_invoice_to_webhook(invoice_id)
Sends invoice data to the webhook endpoint.
- Parameters:
  - invoice_id: ID of the invoice to send
- Returns: Boolean indicating success/failure

### get_partner_ledger(partner_id)
Retrieves ledger entries for a specific partner.
- Parameters:
  - partner_id: ID of the partner
- Returns: List of ledger entries or None if failed

## Error Handling
The script includes comprehensive error handling:
- Connection retry logic
- Data validation
- Network timeout handling
- Automatic reconnection after multiple failures
- Consecutive error tracking

## Webhook Payload Structure
The script sends the following data structure to the webhook:

```json
{
    "event": "new_invoice",
    "operations": [
        {
            "name": "fetch_invoice_details",
            "payload": {
                "invoice": {
                    "invoice_name": "string",
                    "partner": "string",
                    "invoice_date": "date",
                    "invoice_date_due": "date",
                    "amount_total": "float",
                    "amount_residual": "float",
                    "currency": "string",
                    "invoice_lines": [
                        {
                            "product": "string",
                            "quantity": "float",
                            "price_unit": "float",
                            "subtotal": "float"
                        }
                    ],
                    "attachments": [
                        {
                            "id": "integer",
                            "name": "string",
                            "mimetype": "string",
                            "file_size": "integer",
                            "create_date": "datetime",
                            "write_date": "datetime",
                            "type": "string",
                            "url": "string"
                        }
                    ]
                },
                "company_id": 5
            }
        },
        {
            "name": "payment_reminder",
            "payload": {
                "invoice": {
                    "invoice_name": "string",
                    "partner": "string",
                    "amount_residual": "float",
                    "currency": "string",
                    "invoice_date_due": "date"
                },
                "company_id": 5
            }
        },
        {
            "name": "partner_ledger",
            "payload": {
                "partner_id": "integer",
                "partner_name": "string",
                "ledger_entries": [
                    {
                        "id": "integer",
                        "date": "date",
                        "name": "string",
                        "debit": "float",
                        "credit": "float",
                        "balance": "float"
                    }
                ],
                "company_id": 5
            }
        },
        {
            "name": "pdf_invoice",
            "payload": {
                "invoice_id": "integer",
                "invoice_name": "string",
                "pdf_url": "string",
                "company_id": 5
            }
        }
    ]
}
```

## Monitoring and Logging
The script provides detailed logging:
- Connection status
- Invoice processing status
- Error messages
- Webhook responses
- PDF generation status
- Attachment processing status
- Payment reminder status

## Error Recovery
The script implements several recovery mechanisms:
1. Automatic retry for failed operations (3 attempts)
2. Reconnection after 5 consecutive errors
3. 5-minute wait period after failed reconnection
4. Data validation to prevent processing invalid invoices
5. Attachment validation and error handling

## Security
- API keys are required for authentication
- Secure HTTPS connections
- Timeout settings for network requests
- Input validation for all operations
- Secure attachment handling

## Performance
- 1-minute check interval for new invoices
- 5-second delay between processing multiple invoices
- 30-second timeout for network requests
- Efficient data validation and processing
- Optimized attachment handling

## Maintenance
To maintain the script:
1. Regularly update API keys
2. Monitor error logs
3. Check webhook endpoint availability
4. Verify Odoo server connectivity
5. Monitor attachment processing
6. Check payment reminder status

## Troubleshooting
Common issues and solutions:
1. Connection failures:
   - Verify API keys
   - Check network connectivity
   - Ensure Odoo server is running

2. PDF generation failures:
   - Verify PDF API key
   - Check invoice permissions
   - Ensure invoice exists

3. Webhook failures:
   - Verify webhook URL
   - Check payload format
   - Ensure webhook endpoint is accessible

4. Attachment issues:
   - Verify attachment permissions
   - Check file size limits
   - Ensure proper MIME types

5. Payment reminder issues:
   - Verify invoice due dates
   - Check residual amounts
   - Ensure currency information

## Support
For issues or questions:
1. Check error logs
2. Verify configuration
3. Test connectivity
4. Review documentation
5. Check attachment processing
6. Verify payment reminders

## License
[Specify your license here]

## Contributing
[Specify contribution guidelines here]
