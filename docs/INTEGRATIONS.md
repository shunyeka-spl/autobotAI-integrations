## AutobotAI Integrations Overview

The AutobotAI integrations operate on two primary foundations: the Python SDK and Steampipe. Each integration is designed to leverage these technologies for distinct purposes, ensuring flexibility and functionality across different use cases.

### 1. **Steampipe (No-Code Action)**
Steampipe-based integrations are referred to as **No-Code Actions**. These actions are primarily used for data fetching operations, also known as **Fetcher Actions**. They allow users to retrieve data without needing to write custom code, making it easy to gather and analyze information from various sources.

### 2. **Python SDK (Code Action)**
Python-based integrations are designed for more complex operations such as creating, editing, deleting, or executing other custom actions. These **Code Actions** provide users with the ability to perform mutations on data, offering flexibility for tailored automation and processing.

### Overview of Integration Capabilities

Below is a comprehensive overview of the support for both No-Code and Code Actions across the various integrations:


| Integration | Supports No-Code Action | Supports Code Action | How to Integrate |
|:---:|:---:|:---:|:---:|
| <img src="../autobotAI_integrations/integrations/abuseipdb/logo-img/light.svg" alt="AbuseIPDB" width="40" height="40"><br>**AbuseIPDB** | ✅ | ✅ | [link](./integrations/abuseipdb/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/aws/logo-img/light.svg" alt="AWS" width="40" height="40"><br>**AWS** | ✅ | ✅ | [link](./integrations/aws/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/aws_athena/logo-img/light.svg" alt="AWS Athena" width="40" height="40"><br>**AWS Athena** | ❌ | ✅ | [link](./integrations/aws_athena/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/aws_bedrock/logo-img/light.svg" alt="AWS Bedrock" width="40" height="40"><br>**AWS Bedrock** | ❌ | ✅ | [link](./integrations/aws_bedrock/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/aws_security_lake/logo-img/light.svg" alt="AWS Security Lake" width="40" height="40"><br>**AWS Security Lake** | ❌ | ✅ | [link](./integrations/aws_security_lake/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/aws_ses/logo-img/light.svg" alt="AWS SES" width="40" height="40"><br>**AWS SES** | ❌ | ✅ | [link](./integrations/aws_ses/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/azure/logo-img/light.svg" alt="Azure" width="40" height="40"><br>**Azure** | ✅ | ✅ | [link](./integrations/azure/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/azure_entra_id/logo-img/light.svg" alt="Azure Entra ID" width="40" height="40"><br>**Azure Entra ID** | ✅ | ✅ | [link](./integrations/azure_entra_id/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/cloudflare/logo-img/light.svg" alt="Cloudflare" width="40" height="40"><br>**Cloudflare** | ✅ | ❌ | [link](./integrations/cloudflare/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/coralogix/logo-img/light.svg" alt="Coralogix" width="40" height="40"><br>**Coralogix** | ❌ | ✅ | [link](./integrations/coralogix/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/crowdstrike/logo-img/light.svg" alt="CrowdStrike" width="40" height="40"><br>**CrowdStrike** | ✅ | ❌ | [link](./integrations/crowdstrike/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/datadog/logo-img/light.svg" alt="Datadog" width="40" height="40"><br>**Datadog** | ✅ | ✅ | [link](./integrations/datadog/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/email/logo-img/light.svg" alt="Email" width="40" height="40"><br>**Email** | ✅ | ✅ | [link](./integrations/email/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/gcp/logo-img/light.svg" alt="GCP" width="40" height="40"><br>**GCP** | ✅ | ✅ | [link](./integrations/gcp/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/github/logo-img/light.svg" alt="GitHub" width="40" height="40"><br>**GitHub** | ✅ | ✅ | [link](./integrations/github/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/git/logo-img/light.svg" alt="Git" width="40" height="40"><br>**Git** | ❌ | ✅ | [link](./integrations/git/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/gitguardian/logo-img/light.svg" alt="GitGuardian" width="40" height="40"><br>**GitGuardian** | ✅ | ✅ | [link](./integrations/gitguardian/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/gitlab/logo-img/light.svg" alt="GitLab" width="40" height="40"><br>**GitLab** | ✅ | ✅ | [link](./integrations/gitlab/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/grafana/logo-img/light.svg" alt="Grafana" width="40" height="40"><br>**Grafana** | ✅ | ❌ | [link](./integrations/grafana/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/google_chat/logo-img/light.svg" alt="Google Chat" width="40" height="40"><br>**Google Chat** | ❌ | ✅ | [link](./integrations/google_chat/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/ipinfo/logo-img/light.svg" alt="IPInfo" width="40" height="40"><br>**IPInfo** | ✅ | ❌ | [link](./integrations/ipinfo/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/ipstack/logo-img/light.svg" alt="IPStack" width="40" height="40"><br>**IPStack** | ✅ | ❌ | [link](./integrations/ipstack/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/jira/logo-img/light.svg" alt="Jira" width="40" height="40"><br>**Jira** | ✅ | ✅ | [link](./integrations/jira/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/kubernetes/logo-img/light.svg" alt="Kubernetes" width="40" height="40"><br>**Kubernetes** | ✅ | ✅ | [link](./integrations/kubernetes/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/linux/logo-img/light.svg" alt="Linux" width="40" height="40"><br>**Linux** | ✅ | ✅ | [link](./integrations/linux/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/ms_teams/logo-img/light.svg" alt="Microsoft Teams" width="40" height="40"><br>**Microsoft Teams** | ❌ | ✅ | [link](./integrations/ms_teams/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/microsoft_office_365/logo-img/light.svg" alt="Microsoft Office 365" width="40" height="40"><br>**Microsoft Office 365** | ✅ | ✅ | [link](./integrations/microsoft_office_365/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/newrelic/logo-img/light.svg" alt="New Relic" width="40" height="40"><br>**New Relic** | ✅ | ❌ | [link](./integrations/newrelic/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/openai/logo-img/light.svg" alt="OpenAI" width="40" height="40"><br>**OpenAI** | ✅ | ✅ | [link](./integrations/openai/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/ollama/logo-img/light.svg" alt="Ollama" width="40" height="40"><br>**Ollama** | ❌ | ✅ | [link](./integrations/ollama/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/prometheus/logo-img/light.svg" alt="Prometheus" width="40" height="40"><br>**Prometheus** | ✅ | ✅ | [link](./integrations/prometheus/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/python/logo-img/light.svg" alt="Python" width="40" height="40"><br>**Python** | ❌ | ✅ | [link](./integrations/python/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/shodan/logo-img/light.svg" alt="Shodan" width="40" height="40"><br>**Shodan** | ✅ | ✅ | [link](./integrations/shodan/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/slack/logo-img/light.svg" alt="Slack" width="40" height="40"><br>**Slack** | ✅ | ✅ | [link](./integrations/slack/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/splunk/logo-img/light.svg" alt="Splunk" width="40" height="40"><br>**Splunk** | ✅ | ✅ | [link](./integrations/splunk/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/trivy/logo-img/light.svg" alt="Trivy" width="40" height="40"><br>**Trivy** | ✅ | ❌ | [link](./integrations/trivy/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/uptimerobot/logo-img/light.svg" alt="Uptimerobot" width="40" height="40"><br>**Uptimerobot** | ✅ | ❌ | [link](./integrations/uptimerobot/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/urlscan/logo-img/light.svg" alt="URLScan" width="40" height="40"><br>**URLScan** | ✅ | ❌ | [link](./integrations/urlscan/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/virustotal/logo-img/light.svg" alt="VirusTotal" width="40" height="40"><br>**VirusTotal** | ✅ | ✅ | [link](./integrations/virustotal/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/whois/logo-img/light.svg" alt="WHOIS" width="40" height="40"><br>**WHOIS** | ✅ | ❌ | [link](./integrations/whois/Integrate.md)|
| <img src="../autobotAI_integrations/integrations/wiz/logo-img/light.svg" alt="Wiz" width="40" height="40"><br>**Wiz** | ✅ | ❌ | [link](./integrations/wiz/Integrate.md)|
