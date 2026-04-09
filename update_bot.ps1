$projectId = "telegram-autobot-490509"
$region = "asia-northeast3"
$repoName = "telegram-bot-repo"
$imageName = "evening-brief-job"
$jobName = "evening-brief-job"
$imagePath = "${region}-docker.pkg.dev/${projectId}/${repoName}/${imageName}:latest"

Write-Host "1. Docker   ..."
docker build --platform linux/amd64 -t $imagePath .

Write-Host "2. Artifact Registry  ǳ ..."
docker push $imagePath

Write-Host "3. Cloud Run Job  ..."
gcloud run jobs update $jobName `
    --image $imagePath `
    --region $region `
    --max-retries 3 `
    --task-timeout 5m

Write-Host "4. Cloud Run Job  ..."
gcloud run jobs execute $jobName --region $region
