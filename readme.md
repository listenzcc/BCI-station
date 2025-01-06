# BCI Station Sync Script

## Overview

This script copies the `client_base.py` file from the `Control center` folder to the `sync/control_center` folder in each specified target folder.

## Usage

1. Open PowerShell.
2. Navigate to the directory containing the `sync.ps1` script.
3. Run the script using the following command:

    ```powershell
    .\sync.ps1
    ```

## Script Details

```powershell
# Source Path: The path of the file to be copied.
$sourcePath = "Control center\client_base.py"

# Target Folders: The list of folders where the file will be copied.
$folders = @("EEG device side", "HID side")

# Destination Path: The path where the file will be copied in each target folder.
$destinationFolder = "$folder\sync\control_center"
```

## Output

The script provides colored output messages:

- **Green**: Directory creation message.
- **Yellow**: Directory already exists message.
- **Cyan**: File copied message.

## Example Output

```plain text
Creating directory: EEG device side\sync\control_center
Copied to EEG device side\sync\control_center\client_base.py
Directory already exists: HID side\sync\control_center
Copied to HID side\sync\control_center\client_base.py
```
