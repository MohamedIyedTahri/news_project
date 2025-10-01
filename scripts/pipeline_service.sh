#!/bin/bash
#
# News Pipeline Service Management
#
# Provides service-like management for the news extraction pipeline:
# - start: Start the automated pipeline
# - stop: Stop all pipeline processes
# - restart: Restart the pipeline
# - status: Check pipeline status
# - logs: View pipeline logs
# - health: Run health check
#

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_PID_FILE="$PROJECT_ROOT/pipeline.pid"
MONITOR_PID_FILE="$PROJECT_ROOT/monitor.pid"
LOG_DIR="$PROJECT_ROOT/logs"
PIPELINE_LOG="$LOG_DIR/pipeline.log"
MONITOR_LOG="$LOG_DIR/monitor.log"
CONDA_ENV="news-env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if conda environment exists
check_conda_env() {
    if ! conda env list | grep -q "^${CONDA_ENV}"; then
        error "Conda environment '${CONDA_ENV}' not found"
        error "Please create the environment first:"
        error "  conda create -n ${CONDA_ENV} python=3.12"
        error "  conda activate ${CONDA_ENV}"
        error "  pip install -r requirements-kafka.txt"
        exit 1
    fi
}

# Ensure log directory exists
ensure_log_dir() {
    mkdir -p "$LOG_DIR"
}

# Check if process is running
is_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Start Kafka infrastructure
start_kafka() {
    log "Starting Kafka infrastructure..."
    cd "$PROJECT_ROOT"
    
    if docker-compose ps kafka | grep -q "Up"; then
        log "Kafka already running"
    else
        docker-compose up -d
        sleep 10
        
        # Create topics
        if [[ -f "scripts/create_kafka_topics.sh" ]]; then
            bash scripts/create_kafka_topics.sh
        fi
    fi
}

# Stop Kafka infrastructure
stop_kafka() {
    log "Stopping Kafka infrastructure..."
    cd "$PROJECT_ROOT"
    docker-compose down
}

# Start pipeline
start_pipeline() {
    log "Starting news extraction pipeline..."
    
    check_conda_env
    ensure_log_dir
    
    if is_running "$PIPELINE_PID_FILE"; then
        warning "Pipeline already running (PID: $(cat "$PIPELINE_PID_FILE"))"
        return 0
    fi
    
    # Start Kafka
    start_kafka
    
    # Start pipeline in background
    cd "$PROJECT_ROOT"
    
    # Activate conda and start pipeline
    nohup bash -c "
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate ${CONDA_ENV}
        export KAFKA_BOOTSTRAP_SERVERS=localhost:29092
        python scripts/automated_pipeline.py --interval 600
    " > "$PIPELINE_LOG" 2>&1 &
    
    local pipeline_pid=$!
    echo "$pipeline_pid" > "$PIPELINE_PID_FILE"
    
    # Start monitoring in background
    nohup bash -c "
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate ${CONDA_ENV}
        python scripts/monitor_pipeline.py --interval 300
    " > "$MONITOR_LOG" 2>&1 &
    
    local monitor_pid=$!
    echo "$monitor_pid" > "$MONITOR_PID_FILE"
    
    sleep 2
    
    if is_running "$PIPELINE_PID_FILE" && is_running "$MONITOR_PID_FILE"; then
        success "Pipeline started successfully"
        success "  Pipeline PID: $pipeline_pid"
        success "  Monitor PID: $monitor_pid"
        success "  Logs: $PIPELINE_LOG, $MONITOR_LOG"
    else
        error "Failed to start pipeline"
        return 1
    fi
}

# Stop pipeline
stop_pipeline() {
    log "Stopping news extraction pipeline..."
    
    local stopped=false
    
    # Stop pipeline
    if is_running "$PIPELINE_PID_FILE"; then
        local pid=$(cat "$PIPELINE_PID_FILE")
        log "Stopping pipeline (PID: $pid)..."
        
        kill "$pid" 2>/dev/null || true
        sleep 5
        
        if kill -0 "$pid" 2>/dev/null; then
            warning "Force killing pipeline..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        rm -f "$PIPELINE_PID_FILE"
        stopped=true
    fi
    
    # Stop monitor
    if is_running "$MONITOR_PID_FILE"; then
        local pid=$(cat "$MONITOR_PID_FILE")
        log "Stopping monitor (PID: $pid)..."
        
        kill "$pid" 2>/dev/null || true
        sleep 2
        
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        rm -f "$MONITOR_PID_FILE"
        stopped=true
    fi
    
    if $stopped; then
        success "Pipeline stopped"
    else
        warning "Pipeline was not running"
    fi
}

# Restart pipeline
restart_pipeline() {
    log "Restarting news extraction pipeline..."
    stop_pipeline
    sleep 3
    start_pipeline
}

# Check pipeline status
check_status() {
    log "Checking pipeline status..."
    
    local pipeline_running=false
    local monitor_running=false
    
    if is_running "$PIPELINE_PID_FILE"; then
        pipeline_running=true
        success "Pipeline is running (PID: $(cat "$PIPELINE_PID_FILE"))"
    else
        error "Pipeline is not running"
    fi
    
    if is_running "$MONITOR_PID_FILE"; then
        monitor_running=true
        success "Monitor is running (PID: $(cat "$MONITOR_PID_FILE"))"
    else
        error "Monitor is not running"
    fi
    
    # Check Kafka
    if docker-compose ps kafka | grep -q "Up"; then
        success "Kafka infrastructure is running"
    else
        error "Kafka infrastructure is not running"
    fi
    
    # Database stats
    if $pipeline_running || $monitor_running; then
        log "Database statistics:"
        cd "$PROJECT_ROOT"
        if command -v conda >/dev/null 2>&1; then
            source ~/miniconda3/etc/profile.d/conda.sh
            conda activate ${CONDA_ENV} 2>/dev/null || true
            python -m newsbot.db_stats 2>/dev/null || echo "  Unable to get database stats"
        fi
    fi
}

# Show logs
show_logs() {
    local log_type="$1"
    
    case "$log_type" in
        "pipeline"|"")
            if [[ -f "$PIPELINE_LOG" ]]; then
                log "Pipeline logs (last 50 lines):"
                tail -50 "$PIPELINE_LOG"
            else
                warning "No pipeline log found"
            fi
            ;;
        "monitor")
            if [[ -f "$MONITOR_LOG" ]]; then
                log "Monitor logs (last 50 lines):"
                tail -50 "$MONITOR_LOG"
            else
                warning "No monitor log found"
            fi
            ;;
        "all")
            show_logs "pipeline"
            echo
            show_logs "monitor"
            ;;
        *)
            error "Unknown log type: $log_type"
            error "Available types: pipeline, monitor, all"
            exit 1
            ;;
    esac
}

# Run health check
run_health_check() {
    log "Running pipeline health check..."
    
    check_conda_env
    
    cd "$PROJECT_ROOT"
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate ${CONDA_ENV}
    
    python scripts/monitor_pipeline.py --report-only
}

# Install dependencies
install_dependencies() {
    log "Installing pipeline dependencies..."
    
    check_conda_env
    
    cd "$PROJECT_ROOT"
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate ${CONDA_ENV}
    
    # Install required packages
    pip install schedule croniter
    
    if [[ -f "requirements-kafka.txt" ]]; then
        pip install -r requirements-kafka.txt
    fi
    
    success "Dependencies installed"
}

# Show help
show_help() {
    cat << EOF
News Pipeline Service Management

USAGE:
    $0 COMMAND [OPTIONS]

COMMANDS:
    start       Start the automated pipeline and monitoring
    stop        Stop all pipeline processes
    restart     Restart the pipeline
    status      Check pipeline and infrastructure status
    logs [TYPE] Show logs (pipeline|monitor|all, default: pipeline)
    health      Run comprehensive health check
    install     Install required dependencies
    help        Show this help message

EXAMPLES:
    $0 start                    # Start the pipeline
    $0 logs pipeline           # Show pipeline logs
    $0 logs all                # Show all logs
    $0 health                  # Run health check

CONFIGURATION:
    Conda Environment: $CONDA_ENV
    Project Root: $PROJECT_ROOT
    Log Directory: $LOG_DIR

For more information, see the project documentation.
EOF
}

# Main command dispatcher
main() {
    local command="$1"
    local arg="$2"
    
    case "$command" in
        "start")
            start_pipeline
            ;;
        "stop")
            stop_pipeline
            ;;
        "restart")
            restart_pipeline
            ;;
        "status")
            check_status
            ;;
        "logs")
            show_logs "$arg"
            ;;
        "health")
            run_health_check
            ;;
        "install")
            install_dependencies
            ;;
        "help"|"--help"|"-h"|"")
            show_help
            ;;
        *)
            error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"