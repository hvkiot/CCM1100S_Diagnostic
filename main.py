"""Main Entry Point for CCM1100S Diagnostic Tool"""

import sys
import argparse
from ui.streamlit_app import main


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='CCM1100S Diagnostic Tool')
    parser.add_argument('--mode', choices=['ui', 'cli'], default='ui',
                       help='Run mode: UI (Streamlit) or CLI')
    parser.add_argument('--test', action='store_true',
                       help='Run connection test')
    return parser.parse_args()


def run_cli():
    """Run CLI mode"""
    print("="*60)
    print("CCM1100S Diagnostic Tool - CLI Mode")
    print("="*60)
    
    from core.uds_client import UDSClient
    
    client = UDSClient()
    
    print("\nTesting connection...")
    success, result, _ = client.query_single_frame(0x220F)
    
    if success:
        print(f"✅ Connected - System Voltage: {result}")
    else:
        print(f"❌ Connection failed: {result}")
        return
    
    print("\nAvailable commands:")
    print("  voltage  - Read system voltage")
    print("  firmware - Read firmware version")
    print("  vin      - Read VIN number")
    print("  exit     - Exit")
    
    while True:
        cmd = input("\n> ").strip().lower()
        
        if cmd == 'exit':
            break
        elif cmd == 'voltage':
            success, result, _ = client.query_single_frame(0x220F)
            print(f"System Voltage: {result}")
        elif cmd == 'firmware':
            success, result, _ = client.query_multi_frame(0x220D)
            print(f"Firmware Version: {result}")
        elif cmd == 'vin':
            success, result, _ = client.query_multi_frame(0xF190)
            print(f"VIN: {result}")
        else:
            print("Unknown command")


if __name__ == "__main__":
    args = parse_arguments()
    
    if args.test:
        from core.uds_client import UDSClient
        client = UDSClient()
        success, result, _ = client.query_single_frame(0x220F)
        if success:
            print(f"✅ Connection successful - {result}")
        else:
            print(f"❌ Connection failed - {result}")
    elif args.mode == 'cli':
        run_cli()
    else:
        main()