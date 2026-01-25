# Contract Collector Issue

## Problem
The contract collector is finding contract values, but they're not always the correct CURRENT contract values. This is because Spotrac pages contain multiple contract values:
- Current contract
- Historical contracts  
- Cap hits
- Signing bonuses
- Guaranteed money

## Current Status
- ✅ Contract collector is working and finding values
- ⚠️ Values are sometimes wrong (finding historical or other contract values)
- ❌ Years extraction is not working reliably

## Impact
The scoring pipeline has **fallback estimates** based on position and performance, so even if contract data is missing or incorrect, players will still get reasonable market scores.

## Next Steps
1. Improve contract collector to better identify CURRENT contract
2. Add validation to ensure we're getting the right contract
3. Consider using OverTheCap as primary source instead of Spotrac
4. Or rely on fallback estimates in scoring pipeline (already implemented)

## Workaround
The scoring pipeline already has fallback logic in `_calculate_market_score()` that estimates contract values based on position and performance, so incorrect contract data won't break scoring.
