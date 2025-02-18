# Valibot - AI-Powered Test Automation Bot

Valibot is an intelligent test automation bot that leverages generative AI prompts to execute test cases from JIRA, integrating with Google Sheets for test plans and using Playwright for web portal testing. The framework is designed to be extensible, supporting both web application testing and embedded systems validation through RobotFramework integration.

## Features

- 🤖 AI-powered test execution through generative prompts
- 📊 Automated test case extraction from JIRA and Google Sheets
- 🎭 Web application testing using Playwright
- 🔌 Embedded system testing support via RobotFramework
- 🔄 CI/CD integration ready
- 📝 Detailed test execution reporting
- 🗄️ S3 storage integration for test artifacts

## Architecture

├── engine.py         # Core test execution engine
├── config.json       # Configuration settings
├── valibot.spec     # PyInstaller specification
├── README.md         # This file
├── LICENSE           # License information
├── requirements.txt  # Dependencies
├── setup.py          # Installation script
├── valibot           # Main package directory
│   ├── __init__.py   # Package initialization
│   ├── util.py       # Utility functions
│   ├── mail_process.py # Email processing
│   ├── test_execution.py # Test execution
│   ├── engine.py # Core test execution engine
│   ├── jira_process.py # JIRA integration
│   ├── google_auth.py # Google authentication
│   ├── google_process.py # Google Sheets integration
│   ├── aws_process.py # AWS S3 storage handling

## Prerequisites

- Python 3.9+
- Poetry for dependency management
- JIRA account with API access
- Google Cloud Platform account with Sheets API enabled
- AWS account with S3 access (optional)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/valibot.git
cd valibot
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Configure credentials:
- Create a `config.json` file with your credentials:
```json
{
    "jira_server": "https://your-jira-instance.com",
    "jira_user": "your-email@domain.com",
    "jira_api_key": "your-jira-api-key",
    "api_key": "your-google-api-key"
}
```

## Usage

### Basic Command

```bash
valibot -p "your test prompt here"
```

### Command Line Options

- `-p, --prompt`: Specify the test prompt
- `-f, --file`: Provide prompt from a file
- `-d, --debug`: Enable debug logging
- `-t, --template`: Generate prompt template

### Example Workflow

1. Create a test case in JIRA with steps
2. Attach Google Sheet test plan (optional)
3. Run Valibot with the test prompt:
```bash
valibot -p "execute test XSP-123"
```

## Test Execution Process

1. **JIRA Integration**
   - Fetches test case details from JIRA
   - Extracts attached Google Sheet test plans
   - Parses test steps and requirements

2. **Test Plan Processing**
   - Reads Google Sheet test plans
   - Maps JIRA IDs to test steps
   - Extracts test data and parameters

3. **Test Execution**
   - Launches Playwright for web testing
   - Executes test steps sequentially
   - Records test results and screenshots
   - Uploads artifacts to S3

4. **Reporting**
   - Generates detailed test reports
   - Updates JIRA with results
   - Sends email notifications (optional)

## Embedded Systems Testing

For embedded systems testing (DUTs, firmware, semiconductor boards):

1. Configure RobotFramework test suites
2. Set up communication with remote test servers
3. Define test steps in JIRA/Google Sheets
4. Execute tests through Valibot

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please:
1. Check the documentation
2. Open an issue on GitHub
3. Contact the development team

## Acknowledgments

- Playwright for web automation
- RobotFramework for embedded testing
- Google Cloud Platform
- AWS S3
- JIRA REST API

