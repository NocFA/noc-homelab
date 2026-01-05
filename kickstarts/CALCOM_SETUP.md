# Cal.com Self-Hosted Setup

**Purpose**: Video diagnosis booking system for 061 Tech
**Internal URL**: `http://localhost:3000`
**Production URL**: `https://book.061tech.ie` (when DNS configured)
**Integration**: 061tech website buttons link to `https://book.061tech.ie/video-diagnosis`

---

## Why Cal.com?

061 Tech offers a video diagnosis service - customers book a 30-minute video call to figure out what's wrong with their computer. Cal.com handles:
- Scheduling with availability
- Google Calendar sync (optional)
- Automatic Google Meet links
- Payment collection (optional)
- Email confirmations

---

## Deployment via Docker

Cal.com runs directly via Docker Compose on the Mac (not in a VM).

### Quick Start

```bash
cd /Users/noc/noc-homelab/services/calcom
docker compose up -d
```

### Docker Compose Config

Located at `/Users/noc/noc-homelab/services/calcom/docker-compose.yml`:

```yaml
services:
  calcom:
    image: calcom/cal.com:latest
    platform: linux/amd64
    container_name: calcom
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://calcom:calcom_password@calcom-db:5432/calcom
      - DATABASE_DIRECT_URL=postgresql://calcom:calcom_password@calcom-db:5432/calcom
      - NEXTAUTH_SECRET=1IL0H1VDVky9DGRtLVfpYs92XGBBbuR55gSk08FEx2E=
      - CALENDSO_ENCRYPTION_KEY=XB7wPq/LxoOXJDaAPNqJqW/ZnFM18YHm
      - NEXTAUTH_URL=http://localhost:3000
      - NEXT_PUBLIC_WEBAPP_URL=http://localhost:3000
      - NODE_ENV=production
      - NEXT_PUBLIC_LICENSE_CONSENT=agree
    depends_on:
      calcom-db:
        condition: service_healthy
    networks:
      - calcom-net

  calcom-db:
    image: postgres:15-alpine
    container_name: calcom-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=calcom
      - POSTGRES_PASSWORD=calcom_password
      - POSTGRES_DB=calcom
    volumes:
      - calcom-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U calcom"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - calcom-net

volumes:
  calcom-db-data:

networks:
  calcom-net:
```

**Note**: Uses `platform: linux/amd64` for ARM64 (Apple Silicon) compatibility via emulation.

### Important: Access via localhost:3000

The official Cal.com Docker image has `NEXT_PUBLIC_WEBAPP_URL=http://localhost:3000` baked in at build time. For icons and assets to load correctly, **always access via http://localhost:3000**, not noc-local.

---

## Management Commands

```bash
# Start
cd /Users/noc/noc-homelab/services/calcom && docker compose up -d

# Stop
cd /Users/noc/noc-homelab/services/calcom && docker compose down

# Restart
docker restart calcom

# View logs
docker logs calcom --tail 100

# Follow logs
docker logs calcom -f
```

---

## Initial Setup

1. Go to http://localhost:3000
2. Create admin account (first visit prompts setup)
3. Complete onboarding wizard

---

## Create Video Diagnosis Event Type

This is critical - the 061tech website links to `/video-diagnosis`

1. Go to **Event Types** → **+ New**
2. Configure:
   - **Title**: Video Diagnosis
   - **URL slug**: `video-diagnosis` (MUST match exactly)
   - **Duration**: 30 minutes
   - **Description**: Quick video call to diagnose your computer problem
3. **Location**: Google Meet (requires Google Calendar integration)
4. Save

---

## Google Calendar Integration (Optional)

Requires setting up OAuth credentials in Google Cloud Console.

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project: "Cal.com 061Tech"
3. Enable APIs:
   - Google Calendar API
   - Google Meet API (if using Meet)

### Step 2: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: "Cal.com"
5. Authorized redirect URIs:
   ```
   http://localhost:3000/api/integrations/googlecalendar/callback
   ```
6. Copy client ID and client secret

### Step 3: Add to Docker Compose

Add this environment variable to the calcom service:

```yaml
- GOOGLE_API_CREDENTIALS={"web":{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_SECRET","redirect_uris":["http://localhost:3000/api/integrations/googlecalendar/callback"]}}
```

Then restart: `docker compose down && docker compose up -d`

### Step 4: Connect in Cal.com

1. Go to **Settings** → **Integrations**
2. Find **Google Calendar**
3. Click **Connect**
4. Authorize with your Google account

---

## Production Domain Setup (book.061tech.ie)

When ready for production:

1. Set up reverse proxy (nginx/caddy) pointing to localhost:3000
2. Configure SSL via Let's Encrypt
3. Update DNS: A record for `book.061tech.ie` → server IP
4. Update docker-compose environment:
   ```yaml
   - NEXTAUTH_URL=https://book.061tech.ie
   ```
   Note: NEXT_PUBLIC_WEBAPP_URL cannot be changed at runtime (build-time variable)

---

## Website Integration

The 061tech website has buttons pointing to Cal.com:

| Page | Button | URL |
|------|--------|-----|
| Homepage | "Something else?" card | `https://book.061tech.ie/video-diagnosis` |
| Services | "Book Video Diagnosis" | `https://book.061tech.ie/video-diagnosis` |
| Contact | "Book for €20" | `https://book.061tech.ie/video-diagnosis` |
| Book | Sidebar button | `https://book.061tech.ie/video-diagnosis` |

Once the `video-diagnosis` event type exists and DNS is configured, these links will work.

---

## Troubleshooting

### Icons not loading
- Access via `http://localhost:3000` not `noc-local:3000`
- The official image has localhost:3000 baked in at build time

### Cal.com won't start
```bash
docker logs calcom --tail 50
```

### Database issues
```bash
docker logs calcom-db --tail 50
docker exec calcom-db pg_isready -U calcom
```

### Container keeps restarting
```bash
docker compose down
docker volume rm calcom_calcom-db-data  # Warning: deletes all data
docker compose up -d
```

---

## Backup & Restore

### Backup database
```bash
docker exec calcom-db pg_dump -U calcom calcom > calcom_backup.sql
```

### Restore database
```bash
cat calcom_backup.sql | docker exec -i calcom-db psql -U calcom calcom
```

---

*Kickstart updated: January 2026*
