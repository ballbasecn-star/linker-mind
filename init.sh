#!/bin/bash
#
# Linker Mind - Development Environment Management Script
# ======================================================
#
# A comprehensive development environment setup and management script
# for the Linker Mind second-brain + creative workspace system.
#
# Usage:
#   ./init.sh help              - Show this help message
#   ./init.sh check             - Check environment and dependencies
#   ./init.sh init              - Initialize database
#   ./init.sh migrate           - Migrate data from JSON
#   ./init.sh dev [host] [port] - Start development server (default: 127.0.0.1:5000)
#   ./init.sh prod [host] [port]- Start production server (default: 0.0.0.0:5000)
#   ./init.sh test              - Run tests
#   ./init.sh shell             - Start Flask shell
#   ./init.sh dbinfo            - Show database information
#   ./init.sh commit [msg]       - Quick git commit with standard message format
#   ./init.sh status            - Show project status
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_NAME="Linker Mind"
PROJECT_VERSION="2.0.0"
PYTHON_MIN_VERSION="3.10"
VENV_NAME=".venv"
DEFAULT_DEV_HOST="127.0.0.1"
DEFAULT_DEV_PORT="5000"
DEFAULT_PROD_HOST="0.0.0.0"
DEFAULT_PROD_PORT="5000"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Check Python version
check_python_version() {
    log_section "Checking Python Version"

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        return 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    log_info "Found Python $PYTHON_VERSION"

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        log_error "Python $PYTHON_MIN_VERSION or higher is required"
        return 1
    fi

    log_success "Python version check passed"
    return 0
}

# Check virtual environment
check_venv() {
    log_section "Checking Virtual Environment"

    if [ ! -d "$VENV_NAME" ]; then
        log_warning "Virtual environment not found at $VENV_NAME"
        log_info "Creating virtual environment..."

        python3 -m venv "$VENV_NAME"

        if [ $? -eq 0 ]; then
            log_success "Virtual environment created"
            log_info "Run 'source $VENV_NAME/bin/activate' to activate"
        else
            log_error "Failed to create virtual environment"
            return 1
        fi
    else
        log_success "Virtual environment found at $VENV_NAME"
    fi
}

# Check dependencies
check_dependencies() {
    log_section "Checking Dependencies"

    # Activate venv if exists
    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    # Check if pip list works
    if ! command -v pip &> /dev/null; then
        log_error "pip not found"
        return 1
    fi

    # Core dependencies
    local deps=("flask" "psycopg2-binary" "python-dotenv")
    local optional_deps=("gunicorn" "firecrawl-py" "openai")

    local missing_core=0
    local missing_optional=0

    log_info "Checking core dependencies..."
    for dep in "${deps[@]}"; do
        if pip show "$dep" &> /dev/null; then
            version=$(pip show "$dep" | grep Version | cut -d' ' -f2)
            log_success "  $dep ($version)"
        else
            log_warning "  $dep - NOT INSTALLED"
            ((missing_core++))
        fi
    done

    log_info ""
    log_info "Checking optional dependencies..."
    for dep in "${optional_deps[@]}"; do
        if pip show "$dep" &> /dev/null; then
            version=$(pip show "$dep" | grep Version | cut -d' ' -f2)
            log_success "  $dep ($version)"
        else
            log_warning "  $dep - NOT INSTALLED (optional)"
            ((missing_optional++))
        fi
    done

    if [ $missing_core -gt 0 ]; then
        log_error "Missing $missing_core core dependencies"
        log_info "Install with: pip install -r requirements.txt"
        return 1
    fi

    log_success "Core dependencies check passed"
    if [ $missing_optional -gt 0 ]; then
        log_warning "Some optional dependencies are missing (non-critical)"
    fi

    return 0
}

# Check database connection
check_database() {
    log_section "Checking Database"

    # Activate venv if exists
    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    # Load .env file
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    local db_type=${DB_TYPE:-sqlite}

    log_info "Database type: $db_type"

    if [ "$db_type" = "postgresql" ]; then
        local pg_host=${PGHOST:-localhost}
        local pg_port=${PGPORT:-5432}
        local pg_db=${PGDATABASE:-linker-mind}

        log_info "PostgreSQL config: $pg_host:$pg_port / $pg_db"

        if command -v psql &> /dev/null; then
            if PGPASSWORD=${PGPASSWORD:-} psql -h "$pg_host" -p "$pg_port" -U "${PGUSER:-postgres}" -d "$pg_db" -c "SELECT 1;" &> /dev/null; then
                log_success "PostgreSQL connection successful"
            else
                log_warning "PostgreSQL connection failed (will fall back to SQLite)"
            fi
        else
            log_warning "psql client not found, skipping PostgreSQL check"
        fi
    fi

    # Check SQLite fallback
    if [ -f "linker_mind.db" ]; then
        log_success "SQLite database found: linker_mind.db"
    fi

    return 0
}

# Full environment check
cmd_check() {
    log_section "Linker Mind - Environment Check"
    echo ""
    echo "Project: $PROJECT_NAME v$PROJECT_VERSION"
    echo "Directory: $SCRIPT_DIR"
    echo ""

    local failed=0

    check_python_version || ((failed++))
    check_venv || ((failed++))
    check_dependencies || ((failed++))
    check_database || ((failed++))

    echo ""
    if [ $failed -eq 0 ]; then
        log_success "All checks passed!"
        return 0
    else
        log_error "$failed check(s) failed"
        return 1
    fi
}

# Initialize database
cmd_init() {
    log_section "Initializing Database"

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    log_info "Running database initialization..."
    python3 run.py --init

    if [ $? -eq 0 ]; then
        log_success "Database initialized successfully"
        return 0
    else
        log_error "Database initialization failed"
        return 1
    fi
}

# Migrate data
cmd_migrate() {
    log_section "Migrating Data from JSON"

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    log_info "Running data migration..."
    python3 run.py --migrate

    if [ $? -eq 0 ]; then
        log_success "Data migration completed successfully"
        return 0
    else
        log_error "Data migration failed"
        return 1
    fi
}

# Start development server
cmd_dev() {
    local host=${1:-$DEFAULT_DEV_HOST}
    local port=${2:-$DEFAULT_DEV_PORT}

    log_section "Starting Development Server"
    log_info "Host: $host"
    log_info "Port: $port"
    log_info "URL: http://$host:$port"
    echo ""

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    python3 run.py --host "$host" --port "$port"
}

# Start production server
cmd_prod() {
    local host=${1:-$DEFAULT_PROD_HOST}
    local port=${2:-$DEFAULT_PROD_PORT}

    log_section "Starting Production Server"
    log_info "Host: $host"
    log_info "Port: $port"
    log_warning "Production mode enabled"
    echo ""

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    python3 run.py --prod --host "$host" --port "$port"
}

# Run tests
cmd_test() {
    log_section "Running Tests"

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    if [ -d "tests" ]; then
        log_info "Running test suite..."
        python3 -m pytest tests/ -v
    else
        log_warning "No tests directory found"
        log_info "Creating tests directory structure..."
        mkdir -p tests
        log_info "Tests directory created at tests/"
        return 1
    fi
}

# Flask shell
cmd_shell() {
    log_section "Flask Shell"

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    log_info "Starting Flask interactive shell..."
    export FLASK_APP=run.py
    python3 -m flask shell
}

# Database info
cmd_dbinfo() {
    log_section "Database Information"

    if [ -d "$VENV_NAME" ]; then
        source "$VENV_NAME/bin/activate"
    fi

    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    local db_type=${DB_TYPE:-sqlite}

    echo "Database Type: $db_type"

    if [ "$db_type" = "postgresql" ]; then
        echo "Host: ${PGHOST:-localhost}"
        echo "Port: ${PGPORT:-5432}"
        echo "Database: ${PGDATABASE:-linker-mind}"
        echo "User: ${PGUSER:-postgres}"
    fi

    # Check database file stats
    if [ -f "linker_mind.db" ]; then
        echo ""
        echo "SQLite Database File:"
        local size=$(du -h linker_mind.db | cut -f1)
        echo "  Size: $size"
        echo "  Path: $(pwd)/linker_mind.db"
    fi

    # List database tables
    echo ""
    log_info "Database Tables (13 total):"
    echo "  - contents         - nodes             - node_contents"
    echo "  - notes            - links             - learning_sessions"
    echo "  - review_schedules - creation_projects - citations"
    echo "  - skills           - skill_contents    - inbox"
    echo "  - tags"
}

# Git commit helper
cmd_commit() {
    local msg="$1"

    log_section "Git Commit"

    if [ -z "$msg" ]; then
        log_error "Commit message is required"
        log_info "Usage: ./init.sh commit \"your message here\""
        return 1
    fi

    log_info "Committing changes with standard format..."
    echo ""

    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local formatted_msg="[$timestamp] $msg"

    git add -A
    git commit -m "$formatted_msg"

    if [ $? -eq 0 ]; then
        log_success "Changes committed successfully"
        log_info "Message: $formatted_msg"
        return 0
    else
        log_error "Git commit failed"
        return 1
    fi
}

# Show project status
cmd_status() {
    log_section "Linker Mind - Project Status"

    echo ""
    echo "Project: $PROJECT_NAME v$PROJECT_VERSION"
    echo "Directory: $SCRIPT_DIR"
    echo ""

    # Git status
    if [ -d ".git" ]; then
        echo "Git Status:"
        git -c color.status=always status -sb
        echo ""

        local branch=$(git branch --show-current)
        local commits=$(git rev-list --count HEAD 2>/dev/null || echo "0")
        echo "Branch: $branch"
        echo "Total Commits: $commits"
    else
        log_warning "Not a git repository"
    fi

    echo ""

    # Feature completion
    if [ -f "feature_list.json" ]; then
        echo "Feature Status:"
        if command -v jq &> /dev/null; then
            local total=$(jq '.total_features' feature_list.json)
            local completed=$(jq '.completed_features' feature_list.json)
            local rate=$(jq -r '.completion_rate' feature_list.json)
            echo "  Completed: $completed / $total ($rate)"
        else
            echo "  (Install jq for detailed feature stats)"
        fi
    fi

    echo ""

    # Database info
    echo "Database:"
    local db_type=${DB_TYPE:-sqlite}
    echo "  Type: $db_type"
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    if [ "$db_type" = "postgresql" ]; then
        echo "  PostgreSQL: ${PGHOST}:${PGPORT}/${PGDATABASE}"
    fi
    if [ -f "linker_mind.db" ]; then
        local size=$(du -h linker_mind.db | cut -f1)
        echo "  SQLite: linker_mind.db ($size)"
    fi

    echo ""

    # Recent activity
    if [ -f "claude-progress.txt" ]; then
        echo "Recent Progress (from claude-progress.txt):"
        tail -5 claude-progress.txt | sed 's/^/  /'
    fi
}

# Show help
cmd_help() {
    cat << EOF
$PROJECT_NAME v$PROJECT_VERSION - Development Environment Management
=====================================

Usage: ./init.sh <command> [options]

Commands:
  check [env]          - Check environment and dependencies
  init                - Initialize database
  migrate             - Migrate data from JSON
  dev [host] [port]   - Start development server (default: 127.0.0.1:5000)
  prod [host] [port]  - Start production server (default: 0.0.0.0:5000)
  test                - Run test suite
  shell               - Start Flask interactive shell
  dbinfo              - Show database information
  commit <msg>        - Quick git commit with formatted message
  status              - Show detailed project status
  help                - Show this help message

Examples:
  ./init.sh check                    # Check environment
  ./init.sh dev                      # Start dev server on 127.0.0.1:5000
  ./init.sh dev 0.0.0.0 8000         # Start dev server on all interfaces, port 8000
  ./init.sh prod                     # Start production server
  ./init.sh commit "feat: add user auth"
  ./init.sh status

For more information, see:
  - PROJECT_STATUS.md  - Project status documentation
  - feature_list.json  - Feature completion tracking
  - CLAUDE.md          - Product requirements document

EOF
}

# Main script
main() {
    local command="$1"
    shift || true

    case "$command" in
        check)
            cmd_check
            ;;
        init)
            cmd_init
            ;;
        migrate)
            cmd_migrate
            ;;
        dev)
            cmd_dev "$@"
            ;;
        prod)
            cmd_prod "$@"
            ;;
        test)
            cmd_test
            ;;
        shell)
            cmd_shell
            ;;
        dbinfo)
            cmd_dbinfo
            ;;
        commit)
            cmd_commit "$@"
            ;;
        status)
            cmd_status
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
