from flask import Flask, render_template, jsonify
from web3 import Web3
from datetime import datetime
import csv
import os

app = Flask(__name__)

# Set up Web3 connection with Alchemy
ALCHEMY_URL = "https://eth-mainnet.g.alchemy.com/v2/RO2Tb1bd3ZAsR4den8E_9"
w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

# CSV file for storing historical data
CSV_FILE = 'blob_data.csv'

def init_csv():
    """Create CSV file with headers if it doesn't exist"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'block_number',
                'blob_fee_wei',
                'blob_fee_eth',
                'cost_per_blob_eth',
                'blob_gas_used',
                'block_revenue_eth'
            ])

def save_to_csv(data):
    """Append new data to CSV"""
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            data['timestamp'],
            data['block_number'],
            data['blob_fee_wei_raw'],
            data['blob_fee_eth_raw'],
            data['cost_per_blob_eth_raw'],
            data['blob_gas_used_raw'],
            data['block_revenue_eth_raw']
        ])

def read_csv_data():
    """Read all historical data from CSV"""
    if not os.path.exists(CSV_FILE):
        return []
    
    data = []
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def get_blob_base_fee():
    """Get current blob base fee in wei"""
    result = w3.provider.make_request("eth_blobBaseFee", [])
    return int(result['result'], 16)

def wei_to_eth(wei):
    """Convert wei to ETH"""
    return wei / 1e18

def calculate_cost_per_blob(blob_base_fee_wei):
    """Calculate cost per blob (each blob = 131,072 blob gas)"""
    BLOB_GAS_PER_BLOB = 131072
    cost_wei = blob_base_fee_wei * BLOB_GAS_PER_BLOB
    return wei_to_eth(cost_wei)

def get_block_info():
    """Get latest block and blob usage"""
    block = w3.eth.get_block('latest')
    blob_gas_used = block.get('blobGasUsed', 0)
    return {
        'block_number': block['number'],
        'blob_gas_used': blob_gas_used,
        'timestamp': block['timestamp']
    }

def calculate_block_revenue(blob_base_fee_wei, blob_gas_used):
    """Calculate revenue from blobs in this block"""
    revenue_wei = blob_base_fee_wei * blob_gas_used
    return wei_to_eth(revenue_wei)

def get_blob_metrics():
    """Fetch all blob metrics"""
    # Get blob base fee
    blob_fee_wei = get_blob_base_fee()
    blob_fee_eth = wei_to_eth(blob_fee_wei)
    cost_per_blob = calculate_cost_per_blob(blob_fee_wei)
    
    # Get block info
    block_info = get_block_info()
    
    # Calculate revenue
    block_revenue = calculate_block_revenue(blob_fee_wei, block_info['blob_gas_used'])
    
    # Assume $4k ETH for USD calculations
    ETH_PRICE = 4000
    
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'block_number': block_info['block_number'],
        'blob_fee_wei': f"{blob_fee_wei:,}",
        'blob_fee_eth': f"{blob_fee_eth:.10f}",
        'cost_per_blob_eth': f"{cost_per_blob:.6f}",
        'cost_per_blob_usd': f"${cost_per_blob * ETH_PRICE:.2f}",
        'blob_gas_used': f"{block_info['blob_gas_used']:,}",
        'block_revenue_eth': f"{block_revenue:.6f}",
        'block_revenue_usd': f"${block_revenue * ETH_PRICE:.2f}",
        'fee_is_zero': blob_fee_wei == 0,
        # Raw values for CSV storage
        'blob_fee_wei_raw': blob_fee_wei,
        'blob_fee_eth_raw': blob_fee_eth,
        'cost_per_blob_eth_raw': cost_per_blob,
        'blob_gas_used_raw': block_info['blob_gas_used'],
        'block_revenue_eth_raw': block_revenue
    }
    
    # Save to CSV
    save_to_csv(data)
    
    return data

@app.route('/')
def index():
    """Main page"""
    try:
        data = get_blob_metrics()
        return render_template('index.html', **data)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/data')
def api_data():
    """API endpoint for fetching fresh data"""
    try:
        data = get_blob_metrics()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def api_history():
    """API endpoint for fetching historical data"""
    try:
        data = read_csv_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize CSV file
    init_csv()
    
    # Check connection
    if not w3.is_connected():
        print("❌ Failed to connect to Ethereum node")
        print("Make sure to add your Alchemy API key!")
        exit(1)
    
    print("✓ Connected to Ethereum mainnet")
    print("✓ CSV logging enabled")
    print("Starting Flask app at http://localhost:5000")
    app.run(debug=True, port=5000)