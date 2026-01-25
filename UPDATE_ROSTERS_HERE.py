#!/usr/bin/env python3
"""
UPDATED NBA ROSTERS - Fill this in with current data
Go to https://www.nba.com/[team]/roster for each team

EXAMPLE - Lakers (as of Dec 2025):
Visit: https://www.nba.com/lakers/roster
Copy player names and positions here
"""

NBA_ROSTERS_CURRENT = {
    "Los Angeles Lakers": [
        # TODO: Fill in current Lakers roster
        # Anthony Davis is NOT here (he's on Mavericks!)
        {'name': 'LeBron James', 'position': 'F'},
        {'name': 'Austin Reaves', 'position': 'G'},
        # ... add rest of current roster
    ],
    
    "Dallas Mavericks": [
        # TODO: Fill in current Mavericks roster
        # Anthony Davis IS here now!
        {'name': 'Luka Doncic', 'position': 'G'},
        {'name': 'Anthony Davis', 'position': 'C'},  # Traded from Lakers
        {'name': 'Kyrie Irving', 'position': 'G'},
        # ... add rest
    ],
    
    "Golden State Warriors": [
        {'name': 'Stephen Curry', 'position': 'G'},
        # ... add rest
    ],
    
    # Add all 30 teams...
    # You can copy from:
    # https://www.nba.com/[team]/roster
    # or
    # https://www.basketball-reference.com/teams/[ABBREV]/2026.html
}


def get_updated_rosters():
    """Returns the manually updated rosters"""
    return NBA_ROSTERS_CURRENT


if __name__ == "__main__":
    print("="*70)
    print("MANUAL ROSTER UPDATE TEMPLATE")
    print("="*70)
    print()
    print("Fill in NBA_ROSTERS_CURRENT dict above with current rosters")
    print()
    print("Sources:")
    print("  1. https://www.nba.com/lakers/roster")
    print("  2. https://www.nba.com/mavericks/roster")
    print("  3. etc. for all 30 teams")
    print()
    print("Once filled in, the pipeline will use this data.")
    print("="*70)


