// SUPERSEDED: the supported IaC for Rabt's Azure AI stack is Terraform in infra/terraform/ (see its README).
// This azd/Bicep skeleton is kept for reference only and is not maintained.
// Skeleton — expand for azd up (UAE North preferred where available)
param location string = 'uaenorth'
param namePrefix string = 'rabt'

output message string = 'Provision FHIR, Service Bus, Container Apps, OpenAI, Content Safety, PostgreSQL, Key Vault via modules/ — see solution plan §5.6'
