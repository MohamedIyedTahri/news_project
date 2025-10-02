#!/bin/bash
# Script to run automated pipeline for 90 minutes (1.5 hours) in tmux
# Usage: ./run_pipeline_90min.sh

# Configuration
DURATION_SECONDS=5400  # 90 minutes = 5400 seconds
CYCLE_INTERVAL=600     # 10 minutes between cycles
TMUX_SESSION="news-pipeline-90min"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  News Pipeline 90-Minute Run${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Duration: 90 minutes (5400 seconds)"
echo "  Cycle interval: 10 minutes (600 seconds)"
echo "  Expected cycles: ~9"
echo "  Tmux session: ${TMUX_SESSION}"
echo ""

# Check if tmux session already exists
if tmux has-session -t ${TMUX_SESSION} 2>/dev/null; then
    echo -e "${YELLOW}Warning: Session '${TMUX_SESSION}' already exists!${NC}"
    echo "Options:"
    echo "  1) Attach to existing session: tmux attach -t ${TMUX_SESSION}"
    echo "  2) Kill existing session: tmux kill-session -t ${TMUX_SESSION}"
    echo ""
    read -p "Kill existing session and start new one? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t ${TMUX_SESSION}
        echo "Existing session killed."
    else
        echo "Exiting. Attach with: tmux attach -t ${TMUX_SESSION}"
        exit 0
    fi
fi

# Get absolute path to project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_DIR}/scripts"

echo -e "${GREEN}Starting pipeline in tmux session...${NC}"
echo ""

# Create tmux session and run pipeline with timeout
tmux new-session -d -s ${TMUX_SESSION} -c ${SCRIPTS_DIR} bash -c "
    # Activate conda environment
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate news-env
    
    # Display banner
    echo '========================================'
    echo '  Automated News Pipeline - 90 Minutes'
    echo '========================================'
    echo 'Started at: \$(date)'
    echo 'Will run until: \$(date -d '+90 minutes')'
    echo ''
    
    # Run pipeline with timeout
    timeout ${DURATION_SECONDS} python automated_pipeline.py --interval ${CYCLE_INTERVAL}
    
    EXIT_CODE=\$?
    echo ''
    echo '========================================'
    if [ \$EXIT_CODE -eq 124 ]; then
        echo 'Pipeline completed: 90-minute timeout reached'
    elif [ \$EXIT_CODE -eq 0 ]; then
        echo 'Pipeline exited normally'
    else
        echo 'Pipeline exited with error code: '\$EXIT_CODE
    fi
    echo 'Ended at: \$(date)'
    echo '========================================'
    echo ''
    echo 'Session will remain open. Press Ctrl+D or type exit to close.'
    echo ''
    
    # Keep session alive
    exec bash
"

echo -e "${GREEN}✓ Pipeline started in tmux session: ${TMUX_SESSION}${NC}"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo "  View live output:    tmux attach -t ${TMUX_SESSION}"
echo "  Detach from session: Press Ctrl+B then D"
echo "  Check if running:    tmux ls"
echo "  Kill session:        tmux kill-session -t ${TMUX_SESSION}"
echo ""
echo -e "${BLUE}Monitor Progress:${NC}"
echo "  Database stats:      cd ${PROJECT_DIR} && python -m newsbot.db_stats"
echo "  Watch logs:          tail -f ${SCRIPTS_DIR}/pipeline.log"
echo ""
echo -e "${YELLOW}Note: Pipeline will run for 90 minutes and then stop automatically.${NC}"
echo -e "${YELLOW}Attach to the session to see live progress.${NC}"
echo ""
