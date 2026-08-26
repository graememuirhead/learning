variable "app_name" {
  description = "Base name for all resources (e.g. ryetri)"
  type        = string
  default     = "ryetri"
}

variable "environment" {
  description = "Environment suffix"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

variable "location" {
  description = "Azure region to deploy into"
  type        = string
  default     = "centralus"
}

variable "apple_pass_type_identifier" {
  description = "Apple Pass Type ID"
  type        = string
  default     = "pass.com.ryetriclub.membership"
}

variable "apple_team_identifier" {
  description = "10-character Apple Team ID"
  type        = string
  default     = "YNAZR962LC"
}

variable "apple_pass_certificate_pem" {
  description = "Base64-encoded Apple pass certificate PEM"
  type        = string
  default     = ""
  sensitive   = true
}

variable "apple_pass_key_pem" {
  description = "Base64-encoded Apple pass private key PEM"
  type        = string
  default     = ""
  sensitive   = true
}

variable "apple_wwdr_certificate_pem" {
  description = "Base64-encoded Apple WWDR G3 certificate PEM"
  type        = string
  default     = ""
  sensitive   = true
}

variable "apple_key_password" {
  description = "Password for the Apple pass private key (leave blank if none)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_issuer_id" {
  description = "Google Wallet Issuer ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_class_suffix" {
  description = "Suffix for the Google Wallet class ID"
  type        = string
  default     = "ryetri_membership"
}

variable "google_service_account_json" {
  description = "Base64-encoded Google service account JSON"
  type        = string
  default     = ""
  sensitive   = true
}

variable "logo_filename" {
  description = "Logo filename in the assets/ directory"
  type        = string
  default     = "logo.png"
}
