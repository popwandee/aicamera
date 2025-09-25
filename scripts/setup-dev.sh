#!/bin/bash

# AI Camera Development Setup Script

set -e

echo "🚀 Setting up AI Camera development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Node.js is installed and version
check_node() {
    if command -v node >/dev/null 2>&1; then
        NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
        if [ "$NODE_VERSION" -ge 20 ]; then
            print_success "Node.js $NODE_VERSION detected"
        else
            print_error "Node.js version 20 or higher required. Current: $(node -v)"
            exit 1
        fi
    else
        print_error "Node.js not found. Please install Node.js 20 LTS or higher"
        exit 1
    fi
}

# Check if Docker is installed and running
check_docker() {
    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            print_success "Docker is running"
        else
            print_error "Docker is installed but not running. Please start Docker"
            exit 1
        fi
    else
        print_warning "Docker not found. You can still run services individually"
    fi
}

# Install dependencies
install_dependencies() {
    print_status "Installing workspace dependencies..."
    npm install

    print_status "Installing shared library dependencies..."
    cd services/shared && npm install && npm run build && cd ../..

    print_status "Installing database dependencies..."
    cd database && npm install && cd ..

    print_status "Installing service dependencies..."
    
    for service in api-gateway mqtt-service websocket-service file-service; do
        print_status "Installing $service dependencies..."
        cd services/$service && npm install && cd ../..
    done

    print_status "Installing dashboard dependencies..."
    cd dashboard && npm install && cd ..

    print_success "All dependencies installed"
}

# Setup environment files
setup_environment() {
    print_status "Setting up environment configuration..."
    
    if [ ! -f .env ]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_warning "Please update .env file with your configuration"
    else
        print_success "Environment file already exists"
    fi

    # Create storage directories
    mkdir -p storage/{uploads,thumbnails,previews,temp}
    print_success "Storage directories created"
}

# Setup database
setup_database() {
    print_status "Setting up database..."
    
    # Check if PostgreSQL is running
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
            print_success "PostgreSQL is running"
        else
            print_warning "PostgreSQL not running on localhost:5432"
            print_status "You can start PostgreSQL with Docker: docker-compose up postgres -d"
        fi
    else
        print_warning "PostgreSQL client tools not found"
    fi

    cd database
    
    print_status "Generating Prisma client..."
    npm run generate

    print_status "Running database migrations..."
    if npm run migrate; then
        print_success "Database migrations completed"
    else
        print_warning "Database migrations failed. Make sure PostgreSQL is running"
    fi

    print_status "Seeding database with sample data..."
    if npm run seed; then
        print_success "Database seeded with sample data"
    else
        print_warning "Database seeding failed"
    fi

    cd ..
}

# Setup MQTT broker
setup_mqtt() {
    print_status "Setting up MQTT broker configuration..."
    
    # Create MQTT data and log directories
    mkdir -p data/mosquitto/{data,log}
    
    if command -v mosquitto >/dev/null 2>&1; then
        print_success "Mosquitto is installed locally"
    else
        print_status "Mosquitto not found locally. Will use Docker container"
    fi
}

# Build shared library
build_shared() {
    print_status "Building shared library..."
    cd services/shared
    npm run build
    cd ../..
    print_success "Shared library built"
}

# Main setup process
main() {
    echo "=========================================="
    echo "🤖 AI Camera Development Setup"
    echo "=========================================="
    echo

    # Run checks
    check_node
    check_docker
    
    # Setup steps
    install_dependencies
    setup_environment
    build_shared
    setup_mqtt
    setup_database

    echo
    echo "=========================================="
    print_success "Setup completed successfully! 🎉"
    echo "=========================================="
    echo
    echo "Next steps:"
    echo "1. Update your .env file with your configuration"
    echo "2. Start the services:"
    echo "   - Docker: docker-compose up -d"
    echo "   - Manual: npm run dev"
    echo
    echo "3. Access the application:"
    echo "   - Dashboard: http://localhost:5173"
    echo "   - API Gateway: http://localhost:3000"
    echo "   - API Docs: http://localhost:3000/docs"
    echo
    echo "4. Default credentials:"
    echo "   - Admin: admin@aicamera.com / admin123"
    echo "   - Demo: demo@aicamera.com / demo123"
    echo
}

# Run main function
main