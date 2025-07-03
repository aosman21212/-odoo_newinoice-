# Odoo Financial Transaction Monitor

## Overview
This script provides comprehensive monitoring and processing of financial transactions in an Odoo system. It continuously monitors for new invoices, bills, payments, and refunds, then processes and sends the data to a webhook endpoint for further processing.

## Features
- **Comprehensive Financial Monitoring**: Tracks customer invoices, vendor bills, payments, and refunds
- **Real-time Processing**: Checks for new transactions every minute
- **Rich Data Capture**: Includes detailed transaction information, customer/vendor details, and line items
- **Enhanced Error Handling**: Robust retry mechanisms and detailed error reporting
- **Webhook Integration**: Sends structured data to external systems
- **Partner Information**: Captures complete customer/vendor contact and business details
- **Multi-currency Support**: Handles different currencies and exchange rates
- **Payment Method Tracking**: Monitors payment methods and journals
- **Invoice Line Details**: Captures detailed product and pricing information

## Prerequisites
- Python 3.6 or higher
- Required Python packages:
  - xmlrpc.client
  - requests
  - json
  - datetime
  - time

## Configuration
The script requires the following configuration parameters:

```python
# Odoo connection details
url = 'https://your-odoo-instance.com'
db = 'your-database-name'
username = 'your-username'
api_key = 'your-api-key'

# Webhook endpoint
webhook_url = 'https://your-webhook-endpoint.com/agent/event'
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

The script will:
1. Connect to your Odoo instance
2. Monitor for new financial transactions every minute
3. Process and send data to the webhook endpoint
4. Provide detailed logging and error reporting

## Monitored Transaction Types

### Customer Transactions
- **Customer Invoices**: Outgoing invoices to customers
- **Customer Credit Notes**: Refunds issued to customers
- **Customer Payments**: Payments received from customers

### Vendor Transactions
- **Vendor Invoices**: Incoming bills from suppliers
- **Vendor Refunds**: Refunds received from suppliers
- **Vendor Payments**: Payments made to suppliers

## Data Structure

### Invoice/Bill Information
```json
{
    "id": "integer",
    "name": "string",
    "state": "string",
    "move_type": "string",
    "amount_total": "float",
    "amount_untaxed": "float",
    "amount_tax": "float",
    "invoice_date": "date",
    "invoice_date_due": "date",
    "payment_reference": "string",
    "ref": "string",
    "payment_state": "string",
    "narration": "string"
}
```

### Customer/Vendor Information
```json
{
    "partner_id": "integer",
    "partner_name": "string",
    "partner_email": "string",
    "partner_phone": "string",
    "partner_address": "string",
    "partner_city": "string",
    "partner_vat": "string"
}
```

### Payment Information
```json
{
    "id": "integer",
    "name": "string",
    "state": "string",
    "payment_type": "string",
    "amount": "float",
    "date": "date",
    "payment_method_name": "string",
    "payment_method_code": "string",
    "journal_name": "string",
    "journal_code": "string",
    "journal_type": "string"
}
```

### Invoice Line Details
```json
{
    "invoice_lines": [
        {
            "name": "string",
            "quantity": "float",
            "price_unit": "float",
            "price_subtotal": "float",
            "price_total": "float",
            "product_id": "integer",
            "account_id": "integer",
            "tax_ids": "array",
            "discount": "float"
        }
    ]
}
```

### Currency Information
```json
{
    "currency_id": "integer",
    "currency_name": "string",
    "currency_symbol": "string",
    "currency_position": "string"
}
```

## Main Functions

### connect_to_odoo(max_retries=3, retry_delay=5)
Establishes connection with Odoo server with automatic retry logic.
- **Parameters**:
  - max_retries: Maximum number of connection attempts (default: 3)
  - retry_delay: Delay between retries in seconds (default: 5)
- **Returns**: tuple (common, uid) containing connection objects

### get_todays_records(model_name, domain, fields)
Retrieves records created today with comprehensive related data.
- **Parameters**:
  - model_name: Odoo model name (e.g., 'account.move', 'account.payment')
  - domain: Search domain for filtering records
  - fields: List of fields to retrieve
- **Returns**: List of record dictionaries with enhanced partner and related information

### process_records(model_name, domain, fields, record_type)
Processes records of a specific type with detailed error handling.
- **Parameters**:
  - model_name: Odoo model name
  - domain: Search domain
  - fields: Fields to retrieve
  - record_type: Human-readable record type name
- **Returns**: None (processes and logs results)

### send_to_webhook(payload)
Sends structured data to the webhook endpoint with comprehensive error handling.
- **Parameters**:
  - payload: Dictionary containing the data to send
- **Returns**: Boolean indicating success/failure

## Error Handling and Debugging

### Enhanced Error Reporting
- **Individual Record Processing**: Each record is processed with separate error handling
- **Detailed Logging**: Shows record ID, partner, amount, and processing status
- **Webhook Communication**: Detailed logging of webhook requests and responses
- **Network Error Handling**: Specific handling for timeouts and connection errors
- **Stack Trace Reporting**: Full error details for debugging

### Debug Information
The script provides detailed debugging output:
- Record details (ID, name, partner, amount)
- Payload preparation status
- Webhook URL and payload size
- Response status codes and headers
- Complete error stack traces

## Webhook Payload Structure
The script sends the following data structure to the webhook:

```json
{
    "model": "string",
    "data": {
        "id": "integer",
        "name": "string",
        "state": "string",
        "move_type": "string",
        "amount_total": "float",
        "amount_untaxed": "float",
        "amount_tax": "float",
        "partner_id": "integer",
        "partner_name": "string",
        "partner_email": "string",
        "partner_phone": "string",
        "partner_address": "string",
        "partner_city": "string",
        "partner_vat": "string",
        "invoice_date": "date",
        "invoice_date_due": "date",
        "payment_reference": "string",
        "ref": "string",
        "currency_id": "integer",
        "currency_name": "string",
        "currency_symbol": "string",
        "currency_position": "string",
        "payment_state": "string",
        "invoice_lines": "array",
        "narration": "string",
        "payment_method_name": "string",
        "payment_method_code": "string",
        "journal_name": "string",
        "journal_code": "string",
        "journal_type": "string"
    }
}
```

## Monitoring and Logging
The script provides comprehensive logging:
- **Connection Status**: Odoo server connectivity
- **Transaction Processing**: Status of each transaction type
- **Error Messages**: Detailed error information with stack traces
- **Webhook Responses**: Complete webhook communication details
- **Data Validation**: Field validation and data integrity checks
- **Performance Metrics**: Processing times and success rates

## Performance and Reliability
- **1-minute Check Interval**: Monitors for new transactions every minute
- **Automatic Retry Logic**: Retries failed operations with exponential backoff
- **Connection Recovery**: Automatic reconnection after failures
- **Timeout Handling**: 30-second timeout for webhook requests
- **Error Recovery**: Continues processing other records if one fails
- **Memory Efficient**: Processes records in batches to manage memory usage

## Security Features
- **API Key Authentication**: Secure Odoo server authentication
- **HTTPS Connections**: Secure communication with webhook endpoints
- **Input Validation**: Validates all data before processing
- **Error Sanitization**: Prevents sensitive data exposure in error messages
- **Timeout Protection**: Prevents hanging connections

## Troubleshooting

### Common Issues and Solutions

1. **Connection Failures**:
   - Verify Odoo URL and API credentials
   - Check network connectivity
   - Ensure Odoo server is running and accessible

2. **Field Validation Errors**:
   - Check Odoo version compatibility
   - Verify field names exist in your Odoo instance
   - Review domain filters for accuracy

3. **Webhook Failures**:
   - Verify webhook URL is accessible
   - Check webhook endpoint is accepting POST requests
   - Review payload format and size limits
   - Check authentication requirements

4. **Data Processing Issues**:
   - Review error logs for specific field issues
   - Check partner data completeness
   - Verify currency and payment method configurations

5. **Performance Issues**:
   - Monitor processing times in logs
   - Check for large datasets causing timeouts
   - Review webhook response times

## Maintenance
Regular maintenance tasks:
1. **Monitor Error Logs**: Check for recurring errors
2. **Update API Keys**: Rotate credentials regularly
3. **Verify Webhook Endpoint**: Ensure endpoint is accessible
4. **Check Odoo Connectivity**: Monitor server availability
5. **Review Data Quality**: Ensure partner and transaction data is complete
6. **Performance Monitoring**: Track processing times and success rates

## Support
For issues or questions:
1. Check the detailed error logs provided by the script
2. Verify all configuration parameters
3. Test Odoo connectivity manually
4. Review webhook endpoint accessibility
5. Check field availability in your Odoo instance

## License
[Specify your license here]

## Contributing
[Specify contribution guidelines here]
