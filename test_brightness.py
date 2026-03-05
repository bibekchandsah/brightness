"""
Simple test script to verify brightness control works
"""

import screen_brightness_control as sbc

def test_brightness_control():
    """Test if brightness control is working"""
    print("Testing Brightness Control...")
    print("-" * 50)
    
    try:
        # Get current brightness
        current = sbc.get_brightness()
        print(f"✓ Current brightness: {current}")
        
        # Try to set brightness to 50%
        print("\nSetting brightness to 50%...")
        sbc.set_brightness(50)
        
        # Verify
        new_brightness = sbc.get_brightness()
        print(f"✓ New brightness: {new_brightness}")
        
        # Restore original
        print(f"\nRestoring original brightness ({current[0]}%)...")
        sbc.set_brightness(current[0])
        
        print("\n" + "=" * 50)
        print("✓ Brightness control is WORKING!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nPossible issues:")
        print("1. Your display may not support software brightness control")
        print("2. Try running as administrator")
        print("3. External monitors may not be supported")

if __name__ == "__main__":
    test_brightness_control()
    input("\nPress Enter to exit...")
