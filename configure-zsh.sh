sudo apt-get install zsh
sudo usermod -s /usr/bin/zsh $(whoami)
sudo apt-get install powerline fonts-powerline
sudo apt-get install zsh-theme-powerlevel9k
echo "source /usr/share/powerlevel9k/powerlevel9k.zsh-theme" >> ~/.zshrc
sudo apt-get install zsh-syntax-highlighting
echo "source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" >> ~/.zshrc
sudo chsh -s $(which zsh)
