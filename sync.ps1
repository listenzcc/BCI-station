# This script copies the client_base.py file from the Control center folder
# to the sync/control_center folder in each specified target folder.

# Define the source path of the file to be copied
$sourcePath = "Control center\client_base.py"

# Define the list of target folders
$folders = @("EEG device side", "HID side")

# Loop through each folder in the list
foreach ($folder in $folders) {
    # Define the destination folder path
    $destinationFolder = "$folder\sync\control_center"
    
    # Check if the destination folder exists, if not, create it
    if (-Not (Test-Path -Path $destinationFolder)) {
        Write-Host "Creating directory: $destinationFolder" -ForegroundColor Green
        New-Item -ItemType Directory -Path $destinationFolder
    } else {
        Write-Host "Directory already exists: $destinationFolder" -ForegroundColor Yellow
    }
    
    # Define the destination path for the file
    $destinationPath = "$destinationFolder\client_base.py"
    
    # Copy the file to the destination path
    Copy-Item -Path $sourcePath -Destination $destinationPath -Force
    Write-Host "Copied to $destinationPath" -ForegroundColor Cyan
}
