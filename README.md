# Aware

**Consent-based location sharing and OSINT lookup tool.**

Aware lets users opt-in to share their location with specific people through sharing circles. It also includes OSINT lookup features for IP geolocation, phone number parsing, and username enumeration.

## Features

### Location Sharing
- **User accounts** with secure authentication (JWT + refresh tokens)
- **Sharing circles** - create groups and invite others
- **Consent model** - users must explicitly accept invitations
- **Real-time updates** - see shared locations live
- **Privacy controls** - pause sharing, location history

### OSINT Lookups
- **IP Geolocation** - look up location data for any IP address
- **Phone Info** - parse and validate phone numbers
- **Username Search** - check username availability across 30+ platforms

## Quick Start

### Installation

```bash
# Install with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

### Run the CLI

```bash
# Interactive mode
aware

# Direct commands
aware lookup ip 8.8.8.8
aware lookup phone +14155551234
aware lookup user johndoe
```

### Run the Server

```bash
# Development (SQLite)
aware server start

# With Docker (PostgreSQL + PostGIS)
docker-compose up -d
```

## CLI Commands

```bash
# Server
aware server start              # Start API server
aware server status             # Check server status

# Authentication
aware auth register             # Create account
aware auth login                # Login
aware auth logout               # Logout
aware auth status               # Show login status

# Location Tracking
aware track start               # Start sending location
aware track stop                # Stop sending location
aware track status              # Show tracking status
aware track send LAT LON        # Send manual location

# Sharing Circles
aware circle create "Family"    # Create circle
aware circle list               # List my circles
aware circle invite <name>      # Generate invite code
aware circle join <code>        # Join with code
aware circle leave <name>       # Leave circle
aware circle pause <name>       # Pause sharing
aware circle resume <name>      # Resume sharing
aware circle members <name>     # List members

# View Locations
aware live                      # Live dashboard
aware history                   # Location history

# OSINT Lookups
aware lookup ip 8.8.8.8         # IP geolocation
aware lookup phone +1234567890  # Phone info
aware lookup user johndoe       # Username search
aware lookup myip               # Your public IP
```

## API Endpoints

When running the server, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Login (OAuth2 password flow)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout
- `GET /auth/me` - Current user info

### Devices
- `POST /devices` - Register device
- `GET /devices` - List devices
- `DELETE /devices/{id}` - Remove device

### Locations
- `POST /locations` - Submit location
- `GET /locations/me` - My location history
- `GET /locations/live` - Live shared locations
- `GET /locations/shared` - Shared location history

### Circles
- `POST /circles` - Create circle
- `GET /circles` - List circles
- `POST /circles/{name}/invite` - Create invite
- `POST /circles/join` - Join with code
- `DELETE /circles/{name}/leave` - Leave circle
- `PATCH /circles/{name}/sharing` - Toggle sharing
- `GET /circles/{name}/members` - List members
- `DELETE /circles/{name}` - Delete circle

### Lookups
- `GET /lookup/ip/{ip}` - IP geolocation
- `GET /lookup/phone/{number}` - Phone info
- `POST /lookup/username` - Username search

## Configuration

Environment variables (prefix with `AWARE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./aware.db` | Database connection |
| `SECRET_KEY` | (required in prod) | JWT signing key |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Debug mode |
| `ENVIRONMENT` | `development` | Environment name |

Generate a secret key:
```bash
openssl rand -hex 32
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests

# Type check
pyright
```

## Docker

```bash
# Start with PostgreSQL
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

## License

MIT

## Author

Aware
