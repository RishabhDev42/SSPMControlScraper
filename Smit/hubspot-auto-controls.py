from fileinput import filename
import enum, os

from PIL import Image
from pydantic import BaseModel

from google.genai import types
from google import genai

from dotenv import load_dotenv
load_dotenv()

class Category(enum.Enum):
    IAM = "IAM"
    DLP = "DLP"
    SECURITY = "Security"
    PRODUCTIVITY = "Productivity"

# class SubCategory(enum.Enum):

class SeverityLevel(enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"     
    
class Control(BaseModel):
  application: str
  url:str
  control_subject: str
  description: str
  category: Category
  severity: SeverityLevel
  recommendations: str
  additional_info: str | None = None
#   subcategory: str | None = None

# application = "HubSpot"
# url = "https://app-na2.hubspot.com/ai-settings/<organization_id>"

# Image Uploads to Client Libraries
image_folder = "shots"

content_array = []

# Initialize the Google Gemini client with the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
image_dictionary = {}

# Iterate through the images in the folder and upload them
for filename in os.listdir(image_folder):
    if filename.endswith((".png", ".jpg", ".jpeg")):
        image_path = os.path.join(image_folder, filename)

        image_name = filename.split('.')[0]
        image_dictionary[image_name] = client.files.upload(file=image_path)  # ✅

        content_array.append(image_dictionary[image_name])

        
# Generate the response using the Gemini API
response = client.models.generate_content(

    model="gemini-2.5-flash",
    
    contents = ["""

        You are an expert in SaaS Security Posture Management (SSPM). Given the following section of documentation from a SaaS platform, determine whether it describes a setting or configuration that can be transformed into an SSPM control.
        If it qualifies as an SSPM control: 
        Provide the name of the control
        Provide a description of the control and its rationale in 2-3 lines.
        Suggest the best-fitting category from the following: (Just reason and choose one of the 4 categories, don't add the stuff in brackets, that is just to explain what each category is)
        IAM (Manages digital identities and access rights; ensuring the right individuals have the right resource access at the right time)
        DLP (Prevents unauthorized access or leakage of sensitive data)
        Security (Protection against cybersecurity threats that are external to an organization)
        Productivity (Optimizes users' workflow efficiency and task management)
        Investigate the severity of the suggested control from a SSPM POV from the following:
        Low
        Medium
        High
        Write the resolution details in a user-friendly step-by-step format.
            Respond in the following format:
            Description: <description>
            Category: <category>
            Severity: <severity>
            Resolution Steps:
            1) <step 1>
            2) <step 2>
            3) <step 3>
	   …
        Extract the relevant details and return a structured JSON object in the following format:
        [{
          "name": "[Concise control title]",
          "description": "[What the control is about]",
          "category": "[IAM | DLP | Security | Productivity]",
          "severity": "[Low | Medium | High]"
          "resolution_details": "[Steps or configuration needed to enforce or validate the control]"
        },{...}]
        If it does not qualify as an SSPM control, simply return:
        []
        
        Generate multiple controls if applicable, but ensure each control is distinct and relevant to the provided documentation section.
            
        The response should be a JSON array of objects, each representing a control with the specified fields.
        Ensure the response is well-structured and adheres to the JSON format.


    Example 1:
    Here is an example of a sample response:
    [{
      "application": "Hubspot",
      "url": "https://app-na2.hubspot.com/ai-settings/<organization_id>",
      "control_subject": "Use secure cookies only",
      "description": "By using secure cookies, data is exclusively transmitted over encrypted connections (HTTPS), thereby protecting it from interception by attackers and safeguarding privacy. This prevents man-in-the-middle attacks and aligns with modern web security standards.",
      "category": "Security",
      "severity": "High"
      "recommendations": "["1) Login to HubSpot (app.hubspot.com)",
    "2) Navigate to Settings",
    "3) From the side panel, under Account Management, select Tracking Code",
    "4) Select the Advanced Tracking tab",
    "5) Enable Use secure cookies only"]"
    }],
      "additional_info": "This control ensures that cookies are transmitted securely, preventing unauthorized access to sensitive information. It is crucial for maintaining the integrity and confidentiality of user sessions."
        """       ,
    *content_array
    ],
    config = {
        "response_mime_type": "application/json",
        "response_schema": list[Control],  # Specify the expected response schema
    }
)

# Print the response as a JSON string.
print(response.text)

# Parse the response into a list of Control objects
my_controls: list[Control] = response.parsed