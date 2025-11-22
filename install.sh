#!/bin/bash
# Spotify to Slskd Search Aggregator - Easy Install Script
# This script sets up the application with Docker Compose

set -e

echo "======================================================="
echo "  Spotify to Slskd Search Aggregator - Easy Install"
echo "======================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker and Docker Compose are installed"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓${NC} Created .env file from template"
    echo ""

    echo -e "${BLUE}=== Configuration Required ===${NC}"
    echo "Please edit the .env file and add your Slskd API key"
    echo ""
    echo "To get your API key:"
    echo "  1. Open your Slskd web interface"
    echo "  2. Go to Settings → API Keys"
    echo "  3. Generate a new key or copy an existing one"
    echo ""

    # Optionally prompt for API key
    read -p "Would you like to enter your API key now? (y/n): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your Slskd API key: " api_key
        if [ ! -z "$api_key" ]; then
            sed -i "s/SLSKD_API_KEY=.*/SLSKD_API_KEY=$api_key/" .env
            echo -e "${GREEN}✓${NC} API key saved to .env"
        fi
    else
        echo ""
        echo -e "${YELLOW}Remember to edit .env and add your API key before starting!${NC}"
        echo "  nano .env"
        echo "  # or"
        echo "  vi .env"
        echo ""
    fi
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

# Create data directory
echo ""
echo -e "${YELLOW}Creating data directory...${NC}"
mkdir -p ./data
chmod 777 ./data  # Ensure writable by container
echo -e "${GREEN}✓${NC} Data directory created"

# Ask if user wants to build and start now
echo ""
read -p "Would you like to build and start the application now? (y/n): " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker-compose build

    echo ""
    echo -e "${YELLOW}Starting application...${NC}"
    docker-compose up -d

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "The application is now running!"
    echo ""
    echo -e "${BLUE}Access the web interface at:${NC}"
    echo "  http://localhost:5070"
    echo "  http://$(hostname -I | awk '{print $1}'):5070"
    echo ""
    echo -e "${BLUE}Useful commands:${NC}"
    echo "  docker-compose logs -f     # View logs"
    echo "  docker-compose stop        # Stop the application"
    echo "  docker-compose restart     # Restart the application"
    echo "  docker-compose down        # Stop and remove containers"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Open the web interface in your browser"
    echo "  2. Go to Settings to configure your Slskd connection"
    echo "  3. Upload a Spotify CSV export"
    echo "  4. Start searching for music!"
    echo ""
else
    echo ""
    echo -e "${GREEN}Installation prepared!${NC}"
    echo ""
    echo -e "${BLUE}When you're ready to start:${NC}"
    echo "  1. Edit .env and add your API key (if not done already)"
    echo "  2. Run: docker-compose up -d"
    echo ""
fi

echo "For more information, see README.md"
echo ""
