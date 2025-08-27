# Playwright + n8n Runner (Java)

## Prerequisites

Java 17+ (check: java -version)

Maven 3.8+ (check: mvn -v)

Google Chrome (stable)

Node.js 18+ and npm (check: node -v, npm -v)

### 1) Maven project setup

Add Playwright to your pom.xml:
```
<dependencies>
  <dependency>
    <groupId>com.microsoft.playwright</groupId>
    <artifactId>playwright</artifactId>
    <version>1.48.0</version>
  </dependency>
</dependencies>
```

Compile once to pull deps:
```
mvn -q clean compile
```
### 2) Launch Chrome in remote-debugging mode

Find the profile you want to use (the one that already has your credentials):

Open Chrome → go to chrome://version

Note Profile Path → grab the profile folder name (e.g., Profile 6)

Now start Chrome with remote debugging (replace the profile in each command):

macOS (Terminal)
```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome/Profile 6"
```
Linux
```
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.config/google-chrome/Profile 6"
#### If your binary differs:
/opt/google/chrome/chrome ...   or   chromium ...
```
Windows (PowerShell)
```
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:LOCALAPPDATA\Google\Chrome\User Data\Profile 6"
```

Windows (CMD)
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data\Profile 6"
```

Keep this Chrome window open while running the workflow.
If port 9222 is busy, change it (e.g., 9223) and keep it consistent everywhere.

### 3) Run n8n

Install and start n8n locally:
```
npm install -g n8n
n8n
```

Open http://localhost:5678
 and sign in.

### 4) Import the workflow

In n8n, Create workflow → Import from file and choose workflow.json.

### 5) Configure the Execute Command node

This node runs your Maven Java app that uses Playwright over the Chrome debugging port.

macOS / Linux

Set the command to (edit the three variables only):
```
sh -lc 'set -e
PROJECT_DIR="/path/to/mvn/project"   # folder that contains pom.xml
MAIN_CLASS="com.example.App"         # your Java main
URL="https://example.com"            # target URL

cd "$PROJECT_DIR"
mvn -q clean compile
mvn -q -DskipTests exec:java \
  -Dexec.mainClass="$MAIN_CLASS" \
  -Dexec.args="$URL" \
  1> target/output.html 2> target/mvn.log'
```
Windows (PowerShell)
```
$PROJECT_DIR = "C:\path\to\mvn\project"  # folder that contains pom.xml
$MAIN_CLASS  = "com.example.App"
$URL         = "https://example.com"

Push-Location $PROJECT_DIR
mvn -q clean compile
mvn -q -DskipTests exec:java `
  -Dexec.mainClass=$MAIN_CLASS `
  -Dexec.args="$URL" `
  1> "target/output.html" 2> "target/mvn.log"
Pop-Location
```
Windows (CMD)
```
set "PROJECT_DIR=C:\path\to\mvn\project"
set "MAIN_CLASS=com.example.App"
set "URL=https://example.com"

pushd "%PROJECT_DIR%"
mvn -q clean compile
mvn -q -DskipTests exec:java -Dexec.mainClass=%MAIN_CLASS% -Dexec.args="%URL%" 1> target\output.html 2> target\mvn.log
popd
```

PROJECT_DIR = the directory that contains your pom.xml.
MAIN_CLASS = your Java entry point (e.g., com.example.App).
URL = the page your scraper should open.

### 6) Run the workflow

Ensure the remote-debugging Chrome is still open.

In n8n, click Execute on the workflow.

Output HTML is saved to target/output.html; logs → target/mvn.log.

## Troubleshooting

Chrome didn’t connect? Make sure the Chrome window started with --remote-debugging-port=9222 is open. If you changed the port, your Java code must connect to that port.

Profile not found? Use chrome://version again and double-check the Profile Path. The name is case-sensitive on macOS/Linux.

Maven fails? Run mvn -q clean compile in your project folder and fix any missing JDK/Maven issues first.

Paths with spaces (macOS/Linux): wrap in quotes as shown.

Windows 32-bit Chrome: path may be C:\Program Files (x86)\Google\Chrome\Application\chrome.exe.
