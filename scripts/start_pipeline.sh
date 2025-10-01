#!/bin/bash
#
# Automated News Pipeline Starter
#
# This script sets up the environment and runs the automated news extraction pipeline
# It handles conda environment activation and dependency checking automatically
#

set -e

# Configuration
CONDA_ENV="news-env"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if conda is available
check_conda() {
    if ! command -v conda >/dev/null 2>&1; then
        error "Conda not found. Please install Miniconda or Anaconda first."
        exit 1
    fi
    
    # Source conda
    if [[ -f ~/miniconda3/etc/profile.d/conda.sh ]]; then
        source ~/miniconda3/etc/profile.d/conda.sh
    elif [[ -f ~/anaconda3/etc/profile.d/conda.sh ]]; then
        source ~/anaconda3/etc/profile.d/conda.sh
    fi
}

# Activate environment
activate_env() {
    log "Activating conda environment: $CONDA_ENV"
    
    if ! conda env list | grep -q "^${CONDA_ENV}"; then
        error "Conda environment '$CONDA_ENV' not found"
        error "Create it first with:"
        error "  conda create -n $CONDA_ENV python=3.12"
        error "  conda activate $CONDA_ENV"
        error "  pip install -r requirements-kafka.txt"
        exit 1
    fi
    
    conda activate "$CONDA_ENV"
    success "Environment activated"
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    # Check required Python packages
    local missing=()
    
    python -c "import feedparser" 2>/dev/null || missing+=("feedparser")
    python -c "import confluent_kafka" 2>/dev/null || missing+=("confluent-kafka")
    python -c "import aiokafka" 2>/dev/null || missing+=("aiokafka")
    python -c "import requests" 2>/dev/null || missing+=("requests")
    python -c "import beautifulsoup4" 2>/dev/null || missing+=("beautifulsoup4")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        warning "Missing dependencies: ${missing[*]}"
        log "Installing missing dependencies..."
        pip install "${missing[@]}"
    fi
    
    success "Dependencies checked"
}

# Set environment variables
setup_environment() {
    export KAFKA_BOOTSTRAP_SERVERS="localhost:29092"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    cd "$PROJECT_ROOT"
    log "Environment configured"
}

# Start Kafka infrastructure
start_kafka() {
    log "Starting Kafka infrastructure..."
    
    if docker-compose ps kafka | grep -q "Up"; then
        log "Kafka already running"
    else
        docker-compose up -d
        sleep 10
        
        # Create topics
        if [[ -f "scripts/create_kafka_topics.sh" ]]; then
            bash scripts/create_kafka_topics.sh
        fi
        
        success "Kafka started"
    fi
}

# Show menu
show_menu() {
    echo
    echo "=== News Pipeline Automation ==="
    echo
    echo "Choose an option:"
    echo "1) Quick test (tech + science, 10 articles)"
    echo "2) Single extraction cycle (all categories, 30 articles)"
    echo "3) Custom single extraction"
    echo "4) Continuous extraction (every 10 minutes)"
    echo "5) Custom continuous extraction"
    echo "6) Check database statistics"
    echo "7) Exit"
    echo
}

# Run quick test
run_quick_test() {
    log "Running quick test..."
    python scripts/quick_automation.py --test
}

# Run single extraction
run_single_extraction() {
    local categories="$1"
    local articles="$2"
    
    log "Running single extraction cycle..."
    if [[ -n "$categories" ]]; then
        python scripts/quick_automation.py --categories "$categories" --articles "$articles"
    else
        python scripts/quick_automation.py --articles "$articles"
    fi
}

# Run continuous extraction
run_continuous() {
    local categories="$1"
    local interval="$2"
    local articles="$3"
    
    log "Starting continuous extraction..."
    log "Press Ctrl+C to stop"
    
    local cmd="python scripts/quick_automation.py --continuous --interval $interval --articles $articles"
    if [[ -n "$categories" ]]; then
        cmd="$cmd --categories $categories"
    fi
    
    eval "$cmd"
}

# Show database stats
show_stats() {
    log "Current database statistics:"
    python -m newsbot.db_stats
}

# Get user input
get_categories() {
    echo -n "Categories (comma-separated, or press Enter for all): "
    read -r categories
    echo "$categories"
}

get_articles() {
    echo -n "Max articles per cycle (default 30): "
    read -r articles
    echo "${articles:-30}"
}

get_interval() {
    echo -n "Interval in seconds (default 600): "
    read -r interval
    echo "${interval:-600}"
}

# Main menu loop
main_menu() {
    while true; do
        show_menu
        echo -n "Enter choice [1-7]: "
        read -r choice
        
        case $choice in
            1)
                run_quick_test
                ;;
            2)
                run_single_extraction "" 30
                ;;
            3)
                categories=$(get_categories)
                articles=$(get_articles)
                run_single_extraction "$categories" "$articles"
                ;;
            4)
                run_continuous "" 600 30
                ;;
            5)
                categories=$(get_categories)
                interval=$(get_interval)
                articles=$(get_articles)
                run_continuous "$categories" "$interval" "$articles"
                ;;
            6)
                show_stats
                ;;
            7)
                log "Goodbye!"
                exit 0
                ;;
            *)
                error "Invalid choice. Please enter 1-7."
                ;;
        esac
        
        echo
        echo "Press Enter to continue..."
        read -r
    done
}

# Main execution
main() {
    echo "=== Automated News Pipeline Setup ==="
    echo
    
    # Setup
    check_conda
    activate_env
    check_dependencies
    setup_environment
    start_kafka
    
    success "Setup complete!"
    
    # If arguments provided, run non-interactively
    if [[ $# -gt 0 ]]; then
        case "$1" in
            "test")
                run_quick_test
                ;;
            "single")
                run_single_extraction "${2:-}" "${3:-30}"
                ;;
            "continuous")
                run_continuous "${2:-}" "${3:-600}" "${4:-30}"
                ;;
            "stats")
                show_stats
                ;;
            *)
                error "Unknown command: $1"
                error "Available commands: test, single, continuous, stats"
                exit 1
                ;;
        esac
    else
        # Interactive mode
        main_menu
    fi
}

# Run main function
main "$@"