terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

variable "tenancy_ocid" {}
variable "region" {}
variable "ssh_public_key" {}

provider "oci" {
  region              = var.region
  config_file_profile = "DEFAULT"
}