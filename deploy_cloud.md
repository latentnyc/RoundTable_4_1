# Deploy Cloud Script

## Usage
`./deploy_cloud.ps1 -ProjectID your-project-id`

## Steps
1.  **Build Frontend**: Run `npm run build` in `frontend` directory.
2.  **Build Backend**: Run `docker build` for backend service.
3.  **Deploy Backend**: Push Docker image to Artifact Registry and deploy to Cloud Run.
4.  **Deploy Frontend**: Deploy static files to Firebase Hosting.
