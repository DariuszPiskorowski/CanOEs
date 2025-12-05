# CanOEs - CAN Communication GUI
## User Manual

**Version:** 1.0  
**Date:** December 2025  
**Author:** Dariusz Piskorowski

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Getting Started](#3-getting-started)
4. [Main Interface Overview](#4-main-interface-overview)
5. [Connection Panel](#5-connection-panel)
6. [Send Panel](#6-send-panel)
7. [Received Messages Panel](#7-received-messages-panel)
8. [Tabs Overview](#8-tabs-overview)
   - [Main Tab](#81-main-tab)
   - [Filters Tab](#82-filters-tab)
   - [Periodic Tab](#83-periodic-tab)
   - [Timing Tab](#84-timing-tab)
   - [History Tab](#85-history-tab)
   - [Predefined Tab](#86-predefined-tab)
   - [Grouped Tab](#87-grouped-tab)
9. [Features](#9-features)
   - [Theme Toggle](#91-theme-toggle)
   - [Export Logs](#92-export-logs)
   - [Message Coloring](#93-message-coloring)
   - [ASCII Preview](#94-ascii-preview)
   - [ID Comments](#95-id-comments)
10. [How-To Guides](#10-how-to-guides)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Introduction

**CanOEs** (CAN Open Environment Software) is a graphical user interface for CAN and CAN FD communication using Vector VN1640A hardware. It provides an intuitive way to send, receive, filter, and analyze CAN messages.

### Key Features:
- CAN Classic (up to 8 bytes) and CAN FD (up to 64 bytes) support
- Standard (11-bit) and Extended (29-bit) ID support
- Message filtering by ID, range, or mask
- Periodic message transmission
- Message history and predefined messages
- Dark/Light theme support
- Export logs to TXT file

---

## 2. Requirements

### Hardware:
- Vector VN1640A CAN interface (or compatible VN16xx device)

### Software:
- Windows operating system
- Vector XL Driver Library (vxlapi64.dll)
- Python 3.8 or higher
- Required Python packages:
  - `tkinter` (usually included with Python)

---

## 3. Getting Started

1. **Connect Hardware**: Connect your Vector VN1640A to the computer via USB
2. **Install Drivers**: Ensure Vector drivers are installed
3. **Run Application**: Execute `python can_gui.py`
4. **Select Channel**: Choose the CAN channel (1-4)
5. **Select Mode**: Choose CAN or CAN FD mode
6. **Connect**: Click the "Connect" button

---

## 4. Main Interface Overview

The application window is divided into several sections:

```
┌─────────────────────────────────────────────────────────────┐
│  [Toggle Theme]                              Window Title   │
├─────────────────────────────────────────────────────────────┤
│  CONNECTION PANEL                                           │
│  [Channel] [Baudrate] [Mode] [Connect/Disconnect]          │
├─────────────────────────────────────────────────────────────┤
│  SEND PANEL                                                 │
│  [ID] [Extended] [FD] [BRS] [Data] [Pad 00] [Send]         │
├─────────────────────────────────────────────────────────────┤
│  TABS: [Main] [Filters] [Periodic] [Timing] [History]...   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │              TAB CONTENT AREA                       │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  STATUS BAR: TX: 0  RX: 0  Errors: 0  [Status]             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Connection Panel

Located at the top of the window, this panel controls the connection to the CAN hardware.

### Controls:

| Control | Description |
|---------|-------------|
| **Channel** | Dropdown to select CAN channel (1, 2, 3, or 4). Corresponds to physical channels on VN1640A. |
| **Baudrate** | CAN bus speed selection: 125k, 250k, 500k, 1M bit/s |
| **FD Baudrate** | Data phase baudrate for CAN FD: 1M, 2M, 4M, 5M, 8M bit/s |
| **CAN FD Checkbox** | Enable CAN FD mode (allows up to 64 bytes per message) |
| **Connect Button** | Establishes connection to selected channel. Changes to "Disconnect" when connected. |

### Connection Status:
- **Disconnected**: Gray status, "Connect" button visible
- **Connected**: Green status, "Disconnect" button visible
- **Error**: Red status with error message

---

## 6. Send Panel

This panel allows you to compose and send CAN messages.

### Controls:

| Control | Description |
|---------|-------------|
| **ID (hex)** | Message ID in hexadecimal (e.g., `123`, `7DF`, `18DA00F1`) |
| **Extended ID** | Checkbox - enable for 29-bit extended CAN ID |
| **FD** | Checkbox - send as CAN FD frame (allows more than 8 bytes) |
| **BRS** | Checkbox - Bit Rate Switch (faster data phase in CAN FD) |
| **Data (hex)** | Message payload in hexadecimal, space-separated (e.g., `01 02 03 04`) |
| **Byte Counter** | Shows current/maximum bytes (e.g., `8/8 bytes` or `8/64 bytes` for FD) |
| **Pad 00** | Button - fills remaining bytes with zeros (to 8 for CAN, 64 for CAN FD) |
| **Send** | Button - transmits the message |

### Data Length Validation:
- **CAN Classic**: Maximum 8 bytes
- **CAN FD**: Maximum 64 bytes
- Counter turns **red** if data exceeds the limit
- Message will not be sent if data is too long

### Examples:

**Standard CAN message:**
- ID: `123`
- Extended ID: ☐ (unchecked)
- FD: ☐ (unchecked)
- Data: `01 02 03 04 05 06 07 08`

**CAN FD message with BRS:**
- ID: `456`
- Extended ID: ☐ (unchecked)
- FD: ☑ (checked)
- BRS: ☑ (checked)
- Data: `01 02 03` → Click "Pad 00" → `01 02 03 00 00 00 ... 00` (64 bytes)

**Extended ID message:**
- ID: `18DA00F1`
- Extended ID: ☑ (checked)
- Data: `02 10 01`

---

## 7. Received Messages Panel

Located in the Main tab, this panel displays all received and transmitted CAN messages.

### Toolbar Buttons:

| Button | Description |
|--------|-------------|
| **▶ Start / ⏹ Stop** | Start or stop receiving messages |
| **Clear** | Clear all messages from the list |
| **Export TXT** | Save message log to a text file |
| **Auto-scroll** | Checkbox - automatically scroll to newest message |
| **Show Time** | Checkbox - display timestamp column |
| **Show ASCII** | Checkbox - display ASCII representation of data |
| **Color Messages** | Checkbox - enable/disable color coding of messages (TX=green, RX=blue, DIAG=orange) |
| **Edit Comments** | Open dialog to add/edit comments for message IDs |

### Message List Columns:

| Column | Description |
|--------|-------------|
| **Time** | Timestamp when message was sent/received |
| **Dir** | Direction: TX (transmitted) or RX (received) |
| **ID** | Message ID in hexadecimal |
| **DLC** | Data Length Code (number of data bytes) |
| **Data** | Message payload in hexadecimal |
| **ASCII** | ASCII representation of data (if enabled) |
| **Flags** | Message flags: EXT (extended), FD, BRS |
| **Comment** | User-defined comment for this ID |

### Message Colors:

| Color | Meaning |
|-------|---------|
| **Green** | TX - Transmitted messages |
| **Blue** | RX - Received messages |
| **Orange** | DIAG - Diagnostic messages (known diagnostic IDs) |
| **Red** | ERR - Error frames |

---

## 8. Tabs Overview

### 8.1 Main Tab

The primary workspace containing:
- Received Messages panel with message list
- Real-time message display
- Message filtering based on active filters

### 8.2 Filters Tab

Create and manage message filters to show or hide specific CAN IDs.

#### Filter Types:

| Type | Description | Example |
|------|-------------|---------|
| **Single** | Match exact ID | ID = `0x123` |
| **Range** | Match ID within range | From `0x100` to `0x1FF` |
| **Mask** | Match IDs using bit mask | Base `0x700`, Mask `0x7F0` matches `0x700-0x70F` |

#### Filter Controls:

| Control | Description |
|---------|-------------|
| **Filter Name** | User-friendly name for the filter |
| **Filter Type** | Single, Range, or Mask |
| **Accept/Reject** | Accept = show matching, Reject = hide matching |
| **Enabled** | Checkbox to enable/disable filter |
| **Add Filter** | Create new filter |
| **Remove Selected** | Delete selected filter |
| **Enable All / Disable All** | Batch enable/disable all filters |

### 8.3 Periodic Tab

Configure messages to be sent automatically at regular intervals.

#### Periodic Message Settings:

| Setting | Description |
|---------|-------------|
| **ID** | Message ID (hex) |
| **Data** | Message payload (hex) |
| **Interval** | Time between sends in milliseconds |
| **Count** | Number of times to send (0 = infinite) |
| **Extended/FD/BRS** | Message flags |

#### Controls:

| Button | Description |
|--------|-------------|
| **Add** | Add new periodic message |
| **Remove** | Remove selected message |
| **Start All** | Start all enabled periodic messages |
| **Stop All** | Stop all periodic messages |

### 8.4 Timing Tab

Configure timing parameters for message transmission.

#### Settings:

| Setting | Description |
|---------|-------------|
| **Min Frame Gap** | Minimum time (ms) between consecutive transmissions |
| **TX Timeout** | Timeout for transmission confirmation |

### 8.5 History Tab

View and resend previously transmitted messages.

#### Features:
- Automatically records all sent messages
- Double-click or select + "Resend" to retransmit
- "Load" button copies message back to Send panel for editing
- "Clear History" removes all history entries

#### Columns:

| Column | Description |
|--------|-------------|
| **Time** | When message was originally sent |
| **ID** | Message ID |
| **Data** | Message payload |
| **Flags** | EXT, FD, BRS flags |

### 8.6 Predefined Tab

Store frequently used messages for quick access.

#### Default Predefined Messages:
- **Diag 0x744** - `02 10 01` (Diagnostic session)
- **Diag 0x744 Extended** - `02 10 03` (Extended session)
- **OBD Engine RPM** - `0x7DF`: `02 01 0C` (Request engine RPM)
- **OBD Vehicle Speed** - `0x7DF`: `02 01 0D` (Request vehicle speed)
- **OBD Coolant Temp** - `0x7DF`: `02 01 05` (Request coolant temperature)
- **Tester Present** - `0x7DF`: `02 3E 00` (Keep session alive)

#### Controls:

| Button | Description |
|--------|-------------|
| **Send** | Transmit selected predefined message |
| **Add Current** | Save current Send panel content as predefined |
| **Remove** | Delete selected predefined message |

### 8.7 Grouped Tab

View message statistics grouped by CAN ID.

#### Columns:

| Column | Description |
|--------|-------------|
| **ID** | Unique message ID |
| **Count** | Number of times this ID was seen |
| **Last Data** | Most recent payload for this ID |
| **Last Time** | Timestamp of most recent message |
| **Comment** | User-defined comment |

#### Controls:

| Button | Description |
|--------|-------------|
| **Refresh** | Update grouped view with latest data |
| **Clear** | Reset all grouped statistics |

---

## 9. Features

### 9.1 Theme Toggle

Click **"Toggle Theme"** button (top-left) to switch between:
- **Light Theme**: White background, dark text
- **Dark Theme**: Dark background, light text (easier on eyes)

### 9.2 Export Logs

1. Click **"Export TXT"** in the toolbar
2. Choose save location and filename
3. File contains all messages in human-readable format:
   ```
   CanOEs - Message Log
   Exported: 2025-12-05 14:30:00
   =====================================
   
   12:00:01.123  TX  0x123  8  01 02 03 04 05 06 07 08  ........  
   12:00:01.456  RX  0x456  4  11 22 33 44              ."3D      Response
   ```

### 9.3 Message Coloring

Messages can be **automatically** color-coded based on their type. This feature is **enabled by default** but can be toggled on/off.

#### How to enable/disable coloring:
1. In the toolbar above the message list, find **"Color Messages"** checkbox
2. ☑ **Checked** = Colors are applied to messages
3. ☐ **Unchecked** = All messages displayed in default color (black/white depending on theme)

#### How it works (when enabled):
- Colors are assigned automatically when messages appear in the list
- No additional configuration needed - it just works!
- Repeated messages without data changes will gradually fade (become grayed out)
- Messages with changing data stay in full color

| Color | Type | When Applied |
|-------|------|--------------|
| 🟢 **Green** | TX | Any message you transmit |
| 🔵 **Blue** | RX | Any message received from the bus |
| 🟠 **Orange** | DIAG | Messages with diagnostic IDs (0x7DF, 0x7E0, 0x7E8, 0x744, 0x74C, 0x700-0x703) |
| 🔴 **Red** | ERR | Error frames |
| 🔘 **Gray** | STALE | Repeated messages with unchanged data (after 5+ repetitions) |

#### Visual Priority:
1. Error frames are always red
2. Diagnostic IDs override TX/RX color (shown in orange)
3. Stale/repeated messages fade to gray regardless of type

#### When to disable coloring:
- When you need maximum readability in certain lighting conditions
- When preparing screenshots for documentation
- When you prefer a cleaner, monochrome look

### 9.4 ASCII Preview

Enable **"Show ASCII"** checkbox to see ASCII representation of data bytes:
- Printable characters (32-126) shown as-is
- Non-printable characters shown as `.`

Example:
- Data: `48 45 4C 4C 4F 00 01 02`
- ASCII: `HELLO...`

### 9.5 ID Comments

Add custom comments to CAN IDs for documentation:

1. Click **"Edit Comments"** button
2. In dialog:
   - Enter ID (hex): `744`
   - Enter Comment: `ECU Diagnostic Request`
   - Click **"Add/Update"**
3. Comments appear in the message list and grouped view

#### Default Comments:
| ID | Comment |
|----|---------|
| 0x7DF | OBD-II Broadcast |
| 0x7E0 | OBD-II ECU Request |
| 0x7E8 | OBD-II ECU Response |
| 0x744 | Diagnostic Request |
| 0x74C | Diagnostic Response |

---

## 10. How-To Guides

This section provides step-by-step instructions for common tasks.

### 10.1 How to Connect to CAN Bus

**Goal:** Establish connection to your CAN network

**Steps:**
1. Plug Vector VN1640A into USB port
2. Wait for Windows to recognize the device
3. Launch CanOEs application
4. In **Connection Panel** (top of window):
   - Select **Channel**: Usually `1` (check your physical connection)
   - Select **Baudrate**: Must match your CAN network (common: 500k)
   - Check **CAN FD** if your network uses CAN FD
   - If CAN FD, select **FD Baudrate** (common: 2M)
5. Click **Connect** button
6. Status bar should show "Connected" in green

**Troubleshooting:**
- If "Channel not found" → check USB connection
- If no messages appear → verify baudrate matches other devices

---

### 10.2 How to Send a CAN Message

**Goal:** Transmit a single CAN message

**Steps:**
1. Ensure you are connected (see 10.1)
2. In **Send Panel**:
   - Enter **ID** in hex (e.g., `123` or `7DF`)
   - Check **Extended ID** if using 29-bit ID
   - Check **FD** for CAN FD message (more than 8 bytes)
   - Check **BRS** for faster data rate (only with FD)
   - Enter **Data** in hex with spaces (e.g., `01 02 03 04`)
3. Click **Send** button

**Example - Standard OBD-II request:**
- ID: `7DF`
- Extended ID: ☐
- FD: ☐
- Data: `02 01 0C` (request engine RPM)

**Example - CAN FD diagnostic:**
- ID: `744`
- Extended ID: ☐
- FD: ☑
- BRS: ☑
- Data: `02 10 01` → Click **Pad 00** → auto-fills to 64 bytes

---

### 10.3 How to Filter Messages

**Goal:** Show only specific CAN IDs

**Scenario:** You only want to see diagnostic responses (0x74C)

**Steps:**
1. Go to **Filters** tab
2. Enter filter details:
   - **Filter Name**: `Diagnostic Response`
   - **Filter Type**: `Single`
   - **Single ID**: `74C`
   - **Accept/Reject**: `Accept` (show matching)
3. Click **Add Filter**
4. Ensure **Enabled** checkbox is checked
5. Return to **Main** tab - only matching messages will appear

**Scenario:** Hide all messages in range 0x100-0x1FF

**Steps:**
1. Go to **Filters** tab
2. Enter filter details:
   - **Filter Name**: `Hide low IDs`
   - **Filter Type**: `Range`
   - **From**: `100`
   - **To**: `1FF`
   - **Accept/Reject**: `Reject` (hide matching)
3. Click **Add Filter**

---

### 10.4 How to Set Up Periodic Messages

**Goal:** Send a message automatically every X milliseconds

**Scenario:** Send "Tester Present" every 2 seconds to keep session alive

**Steps:**
1. Go to **Periodic** tab
2. Enter message details:
   - **ID**: `7DF`
   - **Data**: `02 3E 00`
   - **Interval (ms)**: `2000` (2 seconds)
   - **Count**: `0` (infinite, or enter number for limited sends)
3. Click **Add**
4. Click **Start All** to begin transmission
5. Watch the Main tab - message appears every 2 seconds
6. Click **Stop All** when finished

---

### 10.5 How to Use Message History

**Goal:** Resend a message you sent earlier

**Steps:**
1. Send some messages normally
2. Go to **History** tab
3. You'll see all previously sent messages with timestamps
4. To resend exact same message:
   - Select the message
   - Click **Resend**
5. To modify before sending:
   - Select the message
   - Click **Load** (copies to Send panel)
   - Modify as needed
   - Click **Send**

---

### 10.6 How to Use Predefined Messages

**Goal:** Quickly send frequently used diagnostic messages

**Steps to send predefined:**
1. Go to **Predefined** tab
2. Select a message (e.g., "OBD Engine RPM")
3. Click **Send**

**Steps to add your own predefined:**
1. In **Send Panel**, set up your message (ID, data, flags)
2. Go to **Predefined** tab
3. Click **Add Current**
4. Your message is now saved for quick access

---

### 10.7 How to Monitor Specific ECU Communication

**Goal:** Analyze communication with a specific ECU (e.g., diagnostic tool ↔ ECU)

**Scenario:** Monitor diagnostic session with ECU using IDs 0x744 (request) and 0x74C (response)

**Steps:**
1. Connect to CAN bus
2. Go to **Filters** tab
3. Add filter for requests:
   - Name: `Diag Request`
   - Type: `Single`
   - ID: `744`
   - Accept: ☑
4. Add filter for responses:
   - Name: `Diag Response`
   - Type: `Single`
   - ID: `74C`
   - Accept: ☑
5. Go to **Main** tab
6. Click **▶ Start** to begin receiving
7. Enable **Show ASCII** to see text in data
8. Click **Edit Comments** and add:
   - ID `744` → Comment: `ECU Request`
   - ID `74C` → Comment: `ECU Response`
9. Now you see only diagnostic traffic with clear labels

---

### 10.8 How to Export Communication Log

**Goal:** Save all messages to a file for later analysis

**Steps:**
1. Capture the messages you want (receive/send)
2. In the toolbar, click **Export TXT**
3. Choose location and filename
4. Click **Save**

**The file contains:**
```
CanOEs - Message Log
Exported: 2025-12-05 14:30:00
=====================================

Time          Dir  ID       DLC  Data                      ASCII     Flags  Comment
12:00:01.123  TX   0x744    3    02 10 01                  ...              Diag Request
12:00:01.456  RX   0x74C    8    06 50 01 00 19 01 F4 00   .P......         Diag Response
```

---

### 10.9 How to Analyze Message Patterns (Grouped View)

**Goal:** See how often each CAN ID appears and its latest data

**Steps:**
1. Start receiving messages
2. Go to **Grouped** tab
3. Click **Refresh** to see statistics
4. Table shows:
   - How many times each ID was received
   - Last data payload for each ID
   - Last timestamp
5. Use this to identify:
   - Most active IDs on the bus
   - Which IDs have changing vs static data
   - Missing expected IDs

---

### 10.10 How to Switch Themes

**Goal:** Change between light and dark mode

**Steps:**
1. Click **Toggle Theme** button (top-left corner)
2. Interface switches between:
   - **Light**: White background (default, good for bright environments)
   - **Dark**: Dark background (reduces eye strain in dim lighting)

---

## 11. Troubleshooting

### Connection Issues

| Problem | Solution |
|---------|----------|
| "Cannot load vxlapi64.dll" | Install Vector driver package |
| "Channel not found" | Check VN1640A is connected and powered |
| "No license" | Ensure valid Vector license is installed |
| "Access denied" | Close other applications using the channel |

### Communication Issues

| Problem | Solution |
|---------|----------|
| No messages received | Check bus termination (120Ω resistors) |
| TX messages fail | Verify baudrate matches other devices |
| CAN FD not working | Ensure all devices support CAN FD |
| Garbled data | Check baudrate settings on all nodes |

### Application Issues

| Problem | Solution |
|---------|----------|
| GUI freezes | Stop receiving, reduce message rate |
| High memory usage | Clear message list periodically |
| Theme not applying | Restart application |

---

## Appendix A: Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` (in Send panel) | Send message |
| `Ctrl+C` | Copy selected messages |
| `Delete` | Remove selected item (in lists) |

---

## Appendix B: CAN FD Data Lengths

Valid CAN FD payload lengths:

| DLC | Bytes |
|-----|-------|
| 0-8 | 0-8 |
| 9 | 12 |
| 10 | 16 |
| 11 | 20 |
| 12 | 24 |
| 13 | 32 |
| 14 | 48 |
| 15 | 64 |

---

## Appendix C: Common Diagnostic IDs

| ID | Description |
|----|-------------|
| 0x7DF | OBD-II functional broadcast address |
| 0x7E0 | OBD-II ECU physical request |
| 0x7E8 | OBD-II ECU physical response |
| 0x700-0x7FF | Standard diagnostic range |
| 0x744 | Common diagnostic request (vehicle-specific) |
| 0x74C | Common diagnostic response (vehicle-specific) |

---

**© 2025 CanOEs Project**
