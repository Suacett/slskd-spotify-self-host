# Download Functionality - Testing Guide

## What Was Fixed

### 1. **Enhanced Logging**
- Added detailed logging to `download_file()` method
- Now logs: URL, payload, API key presence, success/failure status
- Separate error logging for: HTTP errors, connection errors, timeouts, and unexpected errors
- Full traceback logging for debugging

### 2. **Fixed Missing URL Base**
- Added `url_base` parameter to `download_track()` route (line ~1582)
- Added `url_base` parameter to `bulk_download()` route (line ~1633)
- `/download/specific` already had it (line ~1392)

### 3. **Better Error Responses**
- Download routes now return detailed error messages
- Include filename and username in error responses
- Return Slskd API response in success messages

## How to Test

### Prerequisites
1. Ensure Slskd is running and accessible
2. Have search results with at least one track
3. Check that `SLSKD_URL` and `SLSKD_API_KEY` are configured correctly

### Test Steps

#### Test 1: Single Track Download
1. Go to dashboard
2. Click on a track with search results
3. Click the "Download" button
4. **Expected**: Success notification with filename
5. **Check logs** for `[DOWNLOAD]` entries
6. **Verify** in Slskd web UI that download appears in queue

#### Test 2: Specific File Download
1. On track detail page, find a specific result
2. Click download button for that specific file
3. **Expected**: Download initiates
4. **Check logs** for detailed API call information

#### Test 3: Bulk Download
1. Select multiple tracks on dashboard
2. Click "Bulk Download" button
3. **Expected**: Success message with download count
4. **Check logs** for each download attempt

### What to Look For in Logs

**Success Pattern:**
```
[DOWNLOAD] Initiating download: filename.mp3 from username
[DOWNLOAD] URL: http://...
[DOWNLOAD] Payload: {"files": ["filename.mp3"]}
[DOWNLOAD] API Key present: True
[DOWNLOAD] ✓ Success! Response: {...}
[DOWNLOAD_ROUTE] ✓ Download successful for Artist - Title
```

**Failure Patterns:**

**Connection Error:**
```
[DOWNLOAD] ✗ Connection Error: Cannot reach Slskd at http://...
```
→ Check SLSKD_URL is correct and Slskd is running

**HTTP Error:**
```
[DOWNLOAD] ✗ HTTP Error 401
[DOWNLOAD] Response text: Unauthorized
```
→ Check SLSKD_API_KEY is valid

**HTTP Error 404:**
```
[DOWNLOAD] ✗ HTTP Error 404
```
→ Check that url_base is correct (e.g., `/` or `/slskd/`)

**Timeout:**
```
[DOWNLOAD] ✗ Timeout: Request took too long
```
→ Slskd may be slow or unresponsive

## Common Issues & Solutions

### Issue: "Cannot reach Slskd"
**Solution**: 
- Verify Slskd is running
- Check SLSKD_URL is correct
- Test: `curl http://YOUR_SLSKD_URL/api/v0/application`

### Issue: "HTTP Error 401 Unauthorized"
**Solution**:
- Check SLSKD_API_KEY in config.json or environment
- Verify key is valid in Slskd settings

### Issue: "HTTP Error 404"
**Solution**:
- Check SLSKD_URL_BASE setting
- If Slskd is at `http://host:port/`, use url_base: `/`
- If at `http://host:port/slskd/`, use url_base: `/slskd/`

### Issue: Downloads succeed but don't appear in Slskd
**Solution**:
- Check Slskd logs for errors
- Verify user isn't banned/blocked
- Check file path permissions

## Next Steps

If downloads still don't work after these fixes:
1. Share the logs showing `[DOWNLOAD]` entries
2. Test Slskd API directly with curl
3. Check Slskd documentation for API changes
4. Verify network connectivity between containers

## API Endpoint Reference

Slskd download endpoint format:
```
POST {SLSKD_URL}{SLSKD_URL_BASE}api/v0/transfers/downloads/{username}
Body: {"files": ["filename"]}
Headers: {"X-API-Key": "YOUR_API_KEY"}
```

Example:
```bash
curl -X POST \
  "http://192.168.1.124:5030/api/v0/transfers/downloads/someuser" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"files": ["path/to/file.mp3"]}'
```
