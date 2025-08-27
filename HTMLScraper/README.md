install maven, java

First, on the terminal intialize Google Chrome on debugging mode

on MAC:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome/Profile 6"

on Linux:
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.config/google-chrome/Profile 6"

on Windows:

(PowerShell)
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:LOCALAPPDATA\Google\Chrome\User Data\Profile 6"

(CMD)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data\Profile 6"

To find the profile that will run the workflow (and has the credentials in it), go to "chrome://version", and where it says "Profile Path" get the profile number and replace it in the command above.

On terminal (recommended using VSCode):
run the command "n8n"
initialize maven, and in the pom.xml file add this dependencie:
<dependency>
      <groupId>com.microsoft.playwright</groupId>
      <artifactId>playwright</artifactId>
      <version>1.48.0</version> <!-- latest -->
</dependency>

open workflow.json:
on the Execute Command node, add this:

on Mac:
sh -lc 'set -e
PROJECT_DIR="/path/to/mvn/project"   # folder that contains pom.xml
MAIN_CLASS="com.example.App"
URL="https://example" #set URL

cd "$PROJECT_DIR"
mvn -q clean compile
mvn -q -DskipTests exec:java \
  -Dexec.mainClass="$MAIN_CLASS" \
  -Dexec.args="$URL" \
  1> target/output.html 2> target/mvn.log'

on Windows (PowerShell):
$PROJECT_DIR = "C:\path\to\mvn\project"  # folder that contains pom.xml
$MAIN_CLASS  = "com.example.App"
$URL         = "https:/example" #set URL

Push-Location $PROJECT_DIR
mvn -q clean compile
mvn -q -DskipTests exec:java `
  -Dexec.mainClass=$MAIN_CLASS `
  -Dexec.args="$URL" `
  1> "target/output.html" 2> "target/mvn.log"
Pop-Location

on Windows (CMD):
set "PROJECT_DIR=C:\path\to\mvn\project" # folder that contains pom.xml
set "MAIN_CLASS=com.example.App"
set "URL=https://example" #set URL 

pushd "%PROJECT_DIR%"
mvn -q clean compile
mvn -q -DskipTests exec:java -Dexec.mainClass=%MAIN_CLASS% -Dexec.args="%URL%" 1> target\output.html 2> target\mvn.log
popd



