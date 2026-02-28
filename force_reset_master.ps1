Write-Host "Fetching latest updates from origin..."
git fetch origin

Write-Host "Checking out master branch..."
git checkout master

Write-Host "Resetting local master to origin/master..."
git reset --hard origin/master

Write-Host "Done! Local master branch is now synced with remote."
