# Self-Hosted Supabase via Coolify

A guide for deploying Supabase on your homelab using Coolify.

## Overview

**What you get:**
- PostgreSQL database with auto-generated REST & GraphQL APIs
- Authentication (email/password, OAuth, magic links, phone)
- Real-time subscriptions via WebSockets
- Storage with S3-compatible API
- Edge Functions (Deno-based serverless)
- Studio UI for database management

**Requirements:**
- Coolify running (http://noc-local:8000)
- ~4GB RAM recommended for full stack
- ~10GB disk space

## Deployment Steps

### 1. Open Coolify
Navigate to http://noc-local:8000

### 2. Create New Project
- Click "Projects" → "New Project"
- Name it "supabase" or similar

### 3. Add Supabase Service
- In your project, click "New" → "Service"
- Search for "Supabase" in the marketplace
- Select the official Supabase template

### 4. Configure Environment Variables

**Required settings to change:**

```env
# Generate these yourself (use strong random strings)
POSTGRES_PASSWORD=<generate-strong-password>
JWT_SECRET=<generate-32-char-secret>
ANON_KEY=<generate-jwt-anon-key>
SERVICE_ROLE_KEY=<generate-jwt-service-key>

# Your domain/access
SITE_URL=http://noc-local:3000
API_EXTERNAL_URL=http://noc-local:8000

# SMTP for auth emails (optional but recommended)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_SENDER_NAME=Your App
```

**Generate JWT keys:**
```bash
# Generate JWT secret
openssl rand -base64 32

# For ANON_KEY and SERVICE_ROLE_KEY, use Supabase's JWT generator:
# https://supabase.com/docs/guides/self-hosting#api-keys
```

### 5. Configure Ports

Default Supabase ports:
| Service | Port | Purpose |
|---------|------|---------|
| Kong (API Gateway) | 8000 | Main API endpoint |
| Studio | 3000 | Web UI |
| PostgreSQL | 5432 | Direct DB access |
| Realtime | 4000 | WebSocket subscriptions |

**Recommendation:** Change Kong to 8001 to avoid conflict with Coolify UI:
```
KONG_HTTP_PORT=8001
```

### 6. Deploy
Click "Deploy" and wait for all containers to start (~2-5 minutes)

### 7. Access Studio
Open http://noc-local:3000 (or your configured Studio port)

## Connecting Your App

### Update Connection String

**Before (Supabase Cloud):**
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://xxxxx.supabase.co',
  'your-anon-key'
)
```

**After (Self-hosted):**
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'http://noc-local:8001',  // Your Kong API port
  'your-self-hosted-anon-key'
)
```

### Environment Variables for Your App
```env
SUPABASE_URL=http://noc-local:8001
SUPABASE_ANON_KEY=your-generated-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-generated-service-key
DATABASE_URL=postgresql://postgres:your-password@noc-local:5432/postgres
```

## Data Migration

### Export from Supabase Cloud

1. Go to your Supabase Cloud project
2. Settings → Database → Connection string
3. Use `pg_dump` to export:

```bash
pg_dump -h db.xxxxx.supabase.co -U postgres -d postgres -F c -f backup.dump
```

### Import to Self-hosted

```bash
pg_restore -h noc-local -p 5432 -U postgres -d postgres backup.dump
```

### Migrate Auth Users

Auth users are stored in `auth.users` table. The pg_dump above should include them, but verify:

```sql
SELECT count(*) FROM auth.users;
```

## Tailscale Access

Your self-hosted Supabase will be accessible from any Tailscale device:
- Studio: http://noc-local:3000
- API: http://noc-local:8001
- Direct DB: noc-local:5432

## Services Breakdown

Supabase runs multiple containers:

| Container | Purpose | Required |
|-----------|---------|----------|
| supabase-db | PostgreSQL database | Yes |
| supabase-kong | API Gateway | Yes |
| supabase-auth | GoTrue auth server | Yes |
| supabase-rest | PostgREST API | Yes |
| supabase-realtime | WebSocket server | If using real-time |
| supabase-storage | File storage API | If using storage |
| supabase-studio | Web UI | Optional (for admin) |
| supabase-meta | Metadata API | For Studio |
| supabase-edge-functions | Deno runtime | If using functions |

## Resource Usage

Full stack approximate usage:
- **RAM:** 2-4 GB
- **CPU:** 2+ cores recommended
- **Disk:** 5-10 GB base + your data

## Troubleshooting

### Containers not starting
```bash
# Check logs in Coolify UI, or SSH into Coolify VM:
orb -m coolify sudo docker logs supabase-db
orb -m coolify sudo docker logs supabase-kong
```

### Auth not working
- Verify JWT_SECRET matches across services
- Check ANON_KEY and SERVICE_ROLE_KEY are valid JWTs
- Ensure SITE_URL is correct for redirects

### Can't connect from app
- Verify Kong port is exposed and not conflicting
- Check Tailscale is routing correctly
- Test with curl: `curl http://noc-local:8001/rest/v1/`

### Database connection refused
- Ensure PostgreSQL container is healthy
- Check POSTGRES_PASSWORD matches in connection string
- Verify port 5432 is exposed

## Backup Strategy

### Automated Backups (via Coolify)
Coolify can schedule PostgreSQL backups to S3-compatible storage.

### Manual Backup
```bash
# From your Mac
pg_dump -h noc-local -p 5432 -U postgres -d postgres -F c -f supabase_backup_$(date +%Y%m%d).dump
```

## Comparison: Cloud vs Self-hosted

| Feature | Supabase Cloud | Self-hosted |
|---------|---------------|-------------|
| Setup time | 2 minutes | 30-60 minutes |
| Monthly cost | $25+ (Pro) | $0 (your hardware) |
| Maintenance | Managed | You manage |
| Data location | Their servers | Your homelab |
| Backups | Included | You configure |
| Edge Functions | Global CDN | Local only |
| Support | Included | Community |

## Next Steps After Deployment

1. [ ] Verify all services are running in Coolify
2. [ ] Access Studio and confirm database connectivity
3. [ ] Generate proper JWT keys (don't use defaults!)
4. [ ] Configure SMTP for auth emails
5. [ ] Update your app's environment variables
6. [ ] Test auth flow end-to-end
7. [ ] Migrate data if needed
8. [ ] Set up backup schedule
9. [ ] Add to dashboard monitoring (port check)

## Useful Links

- [Supabase Self-hosting Docs](https://supabase.com/docs/guides/self-hosting)
- [Supabase Docker Guide](https://supabase.com/docs/guides/self-hosting/docker)
- [JWT Key Generator](https://supabase.com/docs/guides/self-hosting#api-keys)
- [Coolify Services Docs](https://coolify.io/docs/services/introduction)
