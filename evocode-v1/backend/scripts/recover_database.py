import os
import sys
import argparse
from datetime import datetime

# Add the backend directory to sys.path so we can import utils
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from utils.db_recovery import reset_stuck_features, reset_specific_feature, get_stuck_features

def print_stuck_features(features):
    """Helper to format and print a list of stuck features."""
    if not features:
        print("✅ No stuck features found.")
        return

    print(f"\nFound {len(features)} stuck features:")
    now = datetime.utcnow()
    for f in features:
        # stuck_since is usually a string like '2026-04-24 14:18:40'
        stuck_since_str = f['stuck_since']
        try:
            # Handle standard SQLite datetime string formats
            if '.' in stuck_since_str:
                stuck_time = datetime.strptime(stuck_since_str, '%Y-%m-%d %H:%M:%S.%f')
            else:
                stuck_time = datetime.strptime(stuck_since_str, '%Y-%m-%d %H:%M:%S')
                
            delta = now - stuck_time
            minutes_stuck = int(delta.total_seconds() / 60)
            time_display = f"stuck for {minutes_stuck} minutes"
        except Exception:
            # Fallback if parsing fails
            time_display = f"stuck since {stuck_since_str}"

        title = f['title'][:50] + "..." if len(f['title']) > 50 else f['title']
        print(f"  - Feature #{f['id']}: '{title}' ({time_display})")
    print("")

def main():
    parser = argparse.ArgumentParser(description="EvoCode Database Recovery Tool")
    
    # Mutually exclusive group for the main action
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Just list stuck features without modifying them")
    group.add_argument("--reset-all", action="store_true", help="Reset all stuck features unconditionally")
    group.add_argument("--auto", action="store_true", help="Auto-reset anything stuck > 5 minutes")
    group.add_argument("--reset-id", type=int, metavar="ID", help="Reset a specific feature by its ID")

    args = parser.parse_args()

    try:
        if args.list:
            print("🔍 Scanning database for orphaned processes...")
            features = get_stuck_features()
            print_stuck_features(features)
            
        elif args.auto or args.reset_all:
            # Our reset_stuck_features logic natively uses the 5-minute auto threshold.
            print("🔄 Attempting to reset orphaned features...")
            features_before = get_stuck_features()
            
            if features_before:
                print_stuck_features(features_before)
                result = reset_stuck_features()
                
                if result.get("reset_count", 0) > 0:
                    print(f"✅ Reset complete. Recovered {result['reset_count']} feature(s).")
                else:
                    print("⚠️ Could not reset features, or none met the criteria.")
            else:
                print("✅ No stuck features required resetting.")

        elif args.reset_id is not None:
            feature_id = args.reset_id
            print(f"🔄 Attempting to force-reset Feature #{feature_id}...")
            result = reset_specific_feature(feature_id)
            
            if result.get("success"):
                print(f"✅ Reset complete. {result.get('message')}")
            else:
                print(f"❌ Reset failed. {result.get('message')}")
                sys.exit(1)

    except Exception as e:
        print(f"\n❌ A critical error occurred: {e}")
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
