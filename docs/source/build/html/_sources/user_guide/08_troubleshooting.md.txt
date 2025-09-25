# **8. Troubleshooting**

This section provides solutions to common issues you might encounter while using micro_X.

## **"Ollama Connection Error" / AI Features Not Working**

* **Cause**: The Ollama service that powers the AI features is not running or is unreachable.  
* **Solution**:  
  1. Ensure the Ollama application/service is running on your machine.  
  2. Within micro_X, use the /ollama status command to check the service's status.  
  3. If it's not running, try starting it with /ollama start.

## **micro_X Halts on Startup with "Integrity Check Failed"**

* **Cause**: This happens on the main or testing branches when your local code has uncommitted changes or is not synchronized with the official repository.  
* **Solution**:  
  1. Open a standard terminal in your micro_X project directory.  
  2. Run git status to see the changes.  
  3. You can either discard your local changes (git reset --hard HEAD — **warning: this deletes uncommitted work**) or commit them on a separate feature branch.  
  4. For development, it's best to switch to the dev branch with git checkout dev, where these checks are not enforced.

## **micro_X Warns About Being "Behind Remote"**

* **Cause**: This happens on the main or testing branches when the official repository has updates that your local version does not.  
* **Solution**: Run the /update command from within micro_X to pull the latest changes.