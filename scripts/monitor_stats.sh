#!/bin/bash
# Monitor database growth during pipeline run
# Usage: ./monitor_stats.sh [interval_seconds]

INTERVAL=${1:-30}  # Default: check every 30 seconds
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "${PROJECT_DIR}"

# Activate conda
source ~/miniconda3/etc/profile.d/conda.sh
conda activate news-env

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Database Growth Monitor${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Checking every ${INTERVAL} seconds. Press Ctrl+C to stop."
echo ""

# Get initial count
PREV_TOTAL=$(python -m newsbot.db_stats --json | python -c "import sys, json; print(json.load(sys.stdin)['overall']['total'])")

while true; do
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Database Growth Monitor${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # Get current stats
    STATS=$(python -m newsbot.db_stats --json)
    CURRENT_TOTAL=$(echo "$STATS" | python -c "import sys, json; print(json.load(sys.stdin)['overall']['total'])")
    
    # Calculate growth
    GROWTH=$((CURRENT_TOTAL - PREV_TOTAL))
    
    if [ $GROWTH -gt 0 ]; then
        echo -e "${GREEN}Growth: +${GROWTH} articles since monitoring started${NC}"
    else
        echo -e "${YELLOW}Growth: 0 articles (feeds may not have new content)${NC}"
    fi
    echo ""
    
    # Display full stats
    python -m newsbot.db_stats
    
    echo ""
    echo "Next check in ${INTERVAL} seconds..."
    sleep ${INTERVAL}
done
