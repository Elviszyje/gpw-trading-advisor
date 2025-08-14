#!/bin/bash
# scripts/setup-github.sh - Setup GitHub repository for GPW Trading Advisor

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="gpw-trading-advisor"
DESCRIPTION="Inteligentny system doradztwa inwestycyjnego dla GPW"
HOMEPAGE="https://your-domain.com"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to setup git repository
setup_git() {
    print_status "Setting up Git repository..."
    
    # Initialize git if not already done
    if [ ! -d ".git" ]; then
        git init
        print_success "Git repository initialized"
    fi
    
    # Create .gitignore if not exists
    if [ ! -f ".gitignore" ]; then
        cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Django
*.log
local_settings.py
db.sqlite3
media/

# Environment variables
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml

# Logs
logs/
*.log

# Temporary files
tmp/
temp/

# Backups
backups/

# Chrome
chrome_driver.log
chromedriver.log

# Node modules (if any)
node_modules/

# Coverage
htmlcov/
.coverage
.coverage.*
coverage.xml

# pytest
.pytest_cache/

# Jupyter
.ipynb_checkpoints/

# Selenium
ghostdriver.log
EOF
        print_success ".gitignore created"
    fi
    
    # Add all files
    git add .
    
    # Initial commit
    if ! git log --oneline -1 >/dev/null 2>&1; then
        git commit -m "feat: initial commit with Docker deployment setup

- Add comprehensive Docker setup with multi-service architecture
- Implement CI/CD pipeline with GitHub Actions
- Add production-ready configuration with security hardening
- Include health checks and monitoring
- Set up PostgreSQL, Redis, Django, Celery, Nginx stack
- Add deployment scripts and documentation"
        print_success "Initial commit created"
    fi
}

# Function to setup GitHub CLI
setup_github_cli() {
    if ! command_exists gh; then
        print_error "GitHub CLI (gh) is not installed"
        print_status "Please install GitHub CLI: https://cli.github.com/"
        print_status "macOS: brew install gh"
        print_status "Ubuntu: sudo apt install gh"
        return 1
    fi
    
    # Check if authenticated
    if ! gh auth status >/dev/null 2>&1; then
        print_status "GitHub CLI authentication required"
        gh auth login
    fi
    
    print_success "GitHub CLI is ready"
}

# Function to create GitHub repository
create_github_repo() {
    print_status "Creating GitHub repository..."
    
    # Check if repo already exists
    if gh repo view "$PROJECT_NAME" >/dev/null 2>&1; then
        print_warning "Repository $PROJECT_NAME already exists"
        return 0
    fi
    
    # Create repository
    gh repo create "$PROJECT_NAME" \
        --description "$DESCRIPTION" \
        --homepage "$HOMEPAGE" \
        --public \
        --clone=false \
        --gitignore="" \
        --license="mit"
    
    print_success "GitHub repository created: $PROJECT_NAME"
}

# Function to setup repository settings
setup_repo_settings() {
    print_status "Configuring repository settings..."
    
    # Enable features
    gh repo edit "$PROJECT_NAME" \
        --enable-issues \
        --enable-projects \
        --enable-wiki \
        --enable-discussions
    
    # Setup branch protection (if on main)
    current_branch=$(git branch --show-current)
    if [ "$current_branch" = "main" ] || [ "$current_branch" = "master" ]; then
        print_status "Setting up branch protection rules..."
        
        # Note: Branch protection requires API calls, we'll document this for manual setup
        print_warning "Please manually configure branch protection rules in GitHub:"
        print_warning "- Require pull request reviews"
        print_warning "- Require status checks to pass"
        print_warning "- Require branches to be up to date"
        print_warning "- Include administrators"
    fi
    
    print_success "Repository settings configured"
}

# Function to setup GitHub secrets
setup_github_secrets() {
    print_status "GitHub Secrets setup required manually:"
    print_warning "Please add these secrets in GitHub repository settings:"
    echo
    echo "Required secrets for CI/CD:"
    echo "  - DOCKER_USERNAME: Your Docker Hub username"
    echo "  - DOCKER_PASSWORD: Your Docker Hub password/token"
    echo "  - TELEGRAM_BOT_TOKEN: Your Telegram bot token"
    echo "  - SECRET_KEY: Django secret key"
    echo
    echo "Optional secrets for production deployment:"
    echo "  - SSH_PRIVATE_KEY: SSH key for deployment server"
    echo "  - HOST: Deployment server hostname"
    echo "  - USERNAME: Deployment server username"
    echo
}

# Function to create initial releases
create_initial_release() {
    print_status "Creating initial release..."
    
    # Tag current commit
    git tag -a "v1.0.0" -m "Initial release

Features:
- Docker containerization with multi-service architecture
- CI/CD pipeline with GitHub Actions
- Production-ready deployment setup
- Technical analysis tools
- Portfolio management
- Telegram notifications
- Health monitoring and logging
- Security hardening"
    
    # Create GitHub release
    gh release create "v1.0.0" \
        --title "GPW Trading Advisor v1.0.0" \
        --notes "🚀 **Initial Release**

## ✨ Features
- **Docker Containerization**: Complete multi-service architecture with PostgreSQL, Redis, Django, Celery, and Nginx
- **CI/CD Pipeline**: Automated testing, building, and deployment with GitHub Actions
- **Technical Analysis**: RSI, MACD, Bollinger Bands, SMA/EMA indicators
- **Portfolio Management**: Track and analyze investment performance
- **Telegram Integration**: Real-time notifications and alerts
- **Security**: Production-ready security configuration with rate limiting and headers
- **Health Monitoring**: Comprehensive health checks and logging
- **Cross-platform**: Support for both x86_64 and ARM64 architectures

## 🛠 Technical Stack
- **Backend**: Django 4.2 with Django REST Framework
- **Database**: PostgreSQL 15 with Redis 7 for caching
- **Task Queue**: Celery with Redis broker
- **Containerization**: Docker with Docker Compose
- **Reverse Proxy**: Nginx with SSL support
- **Frontend**: Bootstrap 5 with Chart.js visualizations

## 📚 Documentation
- Complete deployment documentation included
- Development setup guide
- API documentation
- Contributing guidelines

## 🚀 Quick Start
\`\`\`bash
git clone https://github.com/YOUR_USERNAME/gpw-trading-advisor.git
cd gpw-trading-advisor
cp .env.example .env
make dev-start
\`\`\`

See README.md for detailed setup instructions." \
        --latest
    
    print_success "Initial release v1.0.0 created"
}

# Function to push to remote
push_to_remote() {
    print_status "Pushing to GitHub..."
    
    # Add remote if not exists
    if ! git remote get-url origin >/dev/null 2>&1; then
        gh repo set-default "$PROJECT_NAME"
        git remote add origin "https://github.com/$(gh api user --jq .login)/$PROJECT_NAME.git"
    fi
    
    # Push code and tags
    git push -u origin main
    git push origin --tags
    
    print_success "Code pushed to GitHub"
}

# Function to setup project board
setup_project_board() {
    print_status "Project board setup (manual):"
    print_warning "Please manually create project board with these columns:"
    echo "  - 📋 Backlog"
    echo "  - 🔄 In Progress" 
    echo "  - 👀 In Review"
    echo "  - ✅ Done"
    echo "  - 🐛 Bugs"
    echo "  - 🚀 Ready for Release"
}

# Main setup function
main() {
    echo "🚀 Setting up GPW Trading Advisor on GitHub"
    echo "============================================="
    echo
    
    # Check prerequisites
    if ! command_exists git; then
        print_error "Git is not installed"
        exit 1
    fi
    
    # Setup steps
    setup_git
    echo
    
    setup_github_cli || exit 1
    echo
    
    create_github_repo
    echo
    
    setup_repo_settings
    echo
    
    push_to_remote
    echo
    
    create_initial_release
    echo
    
    setup_github_secrets
    echo
    
    setup_project_board
    echo
    
    print_success "🎉 GitHub setup completed!"
    echo
    print_status "Next steps:"
    echo "1. Configure GitHub secrets (see above)"
    echo "2. Set up branch protection rules"
    echo "3. Create project board"
    echo "4. Invite collaborators"
    echo "5. Configure deployment server"
    echo
    print_status "Repository URL: https://github.com/$(gh api user --jq .login)/$PROJECT_NAME"
}

# Run main function
main "$@"
