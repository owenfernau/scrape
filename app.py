from flask import Flask, render_template, jsonify
from web3 import Web3
from datetime import datetime
import csv
import os
import requests

app = Flask(__name__)

# Set up Web3 connection with Alchemy
ALCHEMY_URL = "https://eth-mainnet.g.alchemy.com/v2/RO2Tb1bd3ZAsR4den8E_9"
w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

# CSV file for storing historical data
CSV_FILE = 'blob_data.csv'

# Cache for ETH price (updates every 5 minutes)
eth_price_cache = {'price': 4000, 'last_update': 0}

def get_eth_price():
    """Fetch current ETH price from CoinGecko"""
    current_time = datetime.now().timestamp()
    
    # Use cached price if less than 5 minutes old
    if current_time - eth_price_cache['last_update'] < 300:
        return eth_price_cache['price']
    
    try:
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd',
            timeout=5
        )
        data = response.json()
        price = data['ethereum']['usd']
        
        # Update cache
        eth_price_cache['price'] = price
        eth_price_cache['last_update'] = current_time
        
        return price
    except Exception as e:
        print(f"Error fetching ETH price: {e}")
        return eth_price_cache['price']  # Return cached price on error

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
                'cost_per_blob_usd',
                'blob_gas_used',
                'block_revenue_eth',
                'block_revenue_usd',
                'base_fee_wei',
                'gas_used',
                'base_fee_burned_eth',
                'base_fee_burned_usd',
                'eth_price'
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
            data['cost_per_blob_usd_raw'],
            data['blob_gas_used_raw'],
            data['block_revenue_eth_raw'],
            data['block_revenue_usd_raw'],
            data['base_fee_wei_raw'],
            data['gas_used_raw'],
            data['base_fee_burned_eth_raw'],
            data['base_fee_burned_usd_raw'],
            data['eth_price']
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

def calculate_annualized_revenue():
    """Calculate annualized revenue based on recent hourly average"""
    data = read_csv_data()
    if len(data) == 0:
        return None
    
    # Check if we have at least 1 hour of data (60 samples at 1/min)
    if len(data) < 60:
        return None
    
    # Get revenue values from recent data
    recent_revenues = []
    for row in data:
        try:
            recent_revenues.append(float(row['block_revenue_usd']))
        except (ValueError, KeyError):
            continue
    
    if not recent_revenues:
        return None
    
    # Calculate average revenue per sample
    avg_revenue_per_sample = sum(recent_revenues) / len(recent_revenues)
    
    # Samples per hour (60 minutes / 1 sample per minute)
    samples_per_hour = 60
    
    # Average hourly revenue
    hourly_revenue = avg_revenue_per_sample * samples_per_hour
    
    # Annualize (hours in a year)
    annualized = hourly_revenue * 8760
    
    return annualized

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
    base_fee_per_gas = block.get('baseFeePerGas', 0)
    gas_used = block.get('gasUsed', 0)
    return {
        'block_number': block['number'],
        'blob_gas_used': blob_gas_used,
        'base_fee_per_gas': base_fee_per_gas,
        'gas_used': gas_used,
        'timestamp': block['timestamp']
    }

def calculate_block_revenue(blob_base_fee_wei, blob_gas_used):
    """Calculate revenue from blobs in this block"""
    revenue_wei = blob_base_fee_wei * blob_gas_used
    return wei_to_eth(revenue_wei)

def get_blob_metrics():
    """Fetch all blob metrics"""
    # Get current ETH price
    eth_price = get_eth_price()
    
    # Get blob base fee
    blob_fee_wei = get_blob_base_fee()
    blob_fee_eth = wei_to_eth(blob_fee_wei)
    cost_per_blob = calculate_cost_per_blob(blob_fee_wei)
    
    # Get block info
    block_info = get_block_info()
    
    # Calculate blob revenue
    block_revenue = calculate_block_revenue(blob_fee_wei, block_info['blob_gas_used'])
    
    # Calculate base fee burned (L1 burns)
    base_fee_burned_wei = block_info['base_fee_per_gas'] * block_info['gas_used']
    base_fee_burned_eth = wei_to_eth(base_fee_burned_wei)
    
    # Calculate annualized revenue
    annualized_revenue = calculate_annualized_revenue()
    
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'block_number': block_info['block_number'],
        'eth_price': eth_price,
        'blob_fee_wei': f"{blob_fee_wei:,}",
        'blob_fee_eth': f"{blob_fee_eth:.10f}",
        'blob_fee_usd': f"${blob_fee_eth * eth_price:.8f}",
        'cost_per_blob_eth': f"{cost_per_blob:.6f}",
        'cost_per_blob_usd': f"${cost_per_blob * eth_price:.3f}",
        'blob_gas_used': f"{block_info['blob_gas_used']:,}",
        'block_revenue_eth': f"{block_revenue:.6f}",
        'block_revenue_usd': f"${block_revenue * eth_price:.2f}",
        'base_fee_burned_eth': f"{base_fee_burned_eth:.6f}",
        'base_fee_burned_usd': f"${base_fee_burned_eth * eth_price:.2f}",
        'base_fee_wei': f"{block_info['base_fee_per_gas']:,}",
        'gas_used': f"{block_info['gas_used']:,}",
        'annualized_revenue_usd': f"${annualized_revenue:,.0f}" if annualized_revenue is not None else "Need 1hr+ data",
        'fee_is_zero': blob_fee_wei == 0,
        # Raw values for CSV storage
        'blob_fee_wei_raw': blob_fee_wei,
        'blob_fee_eth_raw': blob_fee_eth,
        'cost_per_blob_eth_raw': cost_per_blob,
        'cost_per_blob_usd_raw': cost_per_blob * eth_price,
        'blob_gas_used_raw': block_info['blob_gas_used'],
        'block_revenue_eth_raw': block_revenue,
        'block_revenue_usd_raw': block_revenue * eth_price,
        'base_fee_wei_raw': block_info['base_fee_per_gas'],
        'gas_used_raw': block_info['gas_used'],
        'base_fee_burned_eth_raw': base_fee_burned_eth,
        'base_fee_burned_usd_raw': base_fee_burned_eth * eth_price
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
    
    # Get initial ETH price
    eth_price = get_eth_price()
    print(f"✓ Connected to Ethereum mainnet")
    print(f"✓ CSV logging enabled")
    print(f"✓ ETH price: ${eth_price:,.2f}")
    print("Starting Flask app at http://localhost:5000")
    app.run(debug=True, port=5000)