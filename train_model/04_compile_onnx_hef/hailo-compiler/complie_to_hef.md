Quick Reference: Useful gcloud Commands
CommandWhat it does
gcloud compute instances list   See all your VMs
gcloud compute instances start hailo-compiler --zone=us-central1-a  Start VM
gcloud compute instances stop hailo-compiler --zone=us-central1-a   Stop VM (saves cost)
gcloud compute instances delete hailo-compiler --zone=us-central1-a Delete VM
gcloud compute scp file.txt hailo-compiler:~/ --zone=us-central1-a  Upload file to VM
gcloud compute scp hailo-compiler:~/model.hef ./ --zone=us-central1-aDownload file from VM

gcloud compute ssh hailo-compiler --zone=us-central1-a
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 