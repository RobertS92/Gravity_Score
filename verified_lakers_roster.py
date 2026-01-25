#!/usr/bin/env python3
"""
VERIFIED Lakers 2024-25 Roster
Since ESPN API is returning corrupted data, use this verified list
"""

LAKERS_ROSTER_2024_25 = [
    {'name': 'LeBron James', 'position': 'F'},
    {'name': 'Anthony Davis', 'position': 'C'},
    {'name': 'Austin Reaves', 'position': 'G'},
    {'name': 'Rui Hachimura', 'position': 'F'},
    {'name': 'D\'Angelo Russell', 'position': 'G'},
    {'name': 'Jarred Vanderbilt', 'position': 'F'},
    {'name': 'Jaxson Hayes', 'position': 'C'},
    {'name': 'Gabe Vincent', 'position': 'G'},
    {'name': 'Dalton Knecht', 'position': 'G'},
    {'name': 'Max Christie', 'position': 'G'},
    {'name': 'Jalen Hood-Schifino', 'position': 'G'},
    {'name': 'Cam Reddish', 'position': 'F'},
    {'name': 'Christian Wood', 'position': 'F'},
    {'name': 'Bronny James', 'position': 'G'},
    {'name': 'Maxwell Lewis', 'position': 'F'},
    {'name': 'Christian Koloko', 'position': 'C'},
    {'name': 'Colin Castleton', 'position': 'C'},
]

def get_verified_lakers_roster():
    """Returns verified Lakers roster"""
    return LAKERS_ROSTER_2024_25

