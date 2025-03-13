# Framework

[toc]

## Routine Center

It is the message center.

- Firstly, it receives the letters and delivers them as the "dst" field. The letter's format is formatted as the `MailMan.mk_letter()` in the [client_base.py](./Routine%20Center/client_base.py). And the `ClientBase` provides the smallest module connecting to the Routine Center.
- Secondly, it automatically convert the "timestamp" field into the dst's time zone.
- Thirdly, it starts the NiceGUI application to review the connected clients.

Since the `MailMan` is used for the clients, I write the sync script to make sure it updates automatically.
See [Appendix: BCI Station Sync Script](#appendix-bci-station-sync-script) for details.

## SSVEP Screen

It is the visual keyboard, flipping on the screen.
The keys flip at certain frequencies, e.g. A: 13Hz, B: 14Hz, ...
The flipping lasts for ~5 seconds, when it starts it send the message to the [Routine Center](#routine-center).
It reads as

```json
// The startup letter.
{
    "id": $uid,
    "src": $ssvepScreenUrl,
    "dst": $eegDeviceUrl,
    "timestamp": $timestamp,
    "action": "SSVEP starts flipping with (without) que",
    "que": "13Hz",
    "requireResponse": true,
}
```

And also, it starts the thread waiting for response.
The thread waits for ~5 seconds (until the next flipping session starts).

- if it receives response at any time, it immediately draw green rectangle to the decoded patch, and mark the letter as *finished*.
- if not, it silently stops, and mark the letter as *error*.

The expected response reads as

```json
// The receive letter.
{
    "id": $uid, // The uid is as the same as the origin request.
    "src": $eegDeviceUrl, // Who ever deals with the request.
    "dst": $ssvepScreenUrl, // Who sent the letter.
    "timestamp": $timestamp,
    "decoded": $decodedFrequency, // Like 13Hz...
}
```

## EEG Device Side

It's main functionality is to read the EEG signal at real time.
In the current implementation, it also receives the SSVEP's letter and decode the frequency.

Basically, when EEG device receives the letter, it does things:

1. Wait for collecting the enough EEG data.
2. Decode the EEG signal for estimating frequency.
3. Fill the "decoded" field.
4. Exchanges the "src" and "dst" fields.
5. Send the letter back.

---

## Appendix: BCI Station Sync Script

### Overview

This script copies the `client_base.py` file from the `Control center` folder to the `sync/control_center` folder in each specified target folder.

### Usage

1. Open PowerShell.
2. Navigate to the directory containing the `sync.ps1` script.
3. Run the script using the following command:

    ```powershell
    .\sync.ps1
    ```

### Script Details

```powershell
# Source Path: The path of the file to be copied.
$sourcePath = "Control center\client_base.py"

# Target Folders: The list of folders where the file will be copied.
$folders = @("EEG device side", "HID side")

# Destination Path: The path where the file will be copied in each target folder.
$destinationFolder = "$folder\sync\control_center"
```

### Output

The script provides colored output messages:

- **Green**: Directory creation message.
- **Yellow**: Directory already exists message.
- **Cyan**: File copied message.

### Example Output

```plain text
Creating directory: EEG device side\sync\control_center
Copied to EEG device side\sync\control_center\client_base.py
Directory already exists: HID side\sync\control_center
Copied to HID side\sync\control_center\client_base.py
```
