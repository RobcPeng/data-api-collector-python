output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.data_api.id
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = aws_instance.data_api.public_ip
}

output "api_url" {
  description = "API base URL"
  value       = "http://${aws_instance.data_api.public_ip}:10800/api/v1"
}

output "neo4j_browser" {
  description = "Neo4j Browser URL"
  value       = "http://${aws_instance.data_api.public_ip}:7474"
}

output "kafka_broker" {
  description = "Kafka external broker address"
  value       = "${aws_instance.data_api.public_ip}:9094"
}

output "postgres_jdbc" {
  description = "PostgreSQL JDBC URL"
  value       = "jdbc:postgresql://${aws_instance.data_api.public_ip}:15433/data_collector?ssl=true&sslmode=require"
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.data_api.public_ip}" : "No SSH key configured"
}

output "setup_log" {
  description = "Command to check bootstrap progress"
  value       = "ssh ubuntu@${aws_instance.data_api.public_ip} 'tail -f /var/log/data-api-collector-setup.log'"
}

output "credentials_command" {
  description = "Command to view credentials on the instance"
  value       = "ssh ubuntu@${aws_instance.data_api.public_ip} './data-api-info.sh'"
}
