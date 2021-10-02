" use vim
set nocompatible
filetype off "required

" no intro message
set shortmess+=I

" set status bar at the bottom
set laststatus=2
set statusline+=\ %<%F\                           " file path
set statusline+=\ %=\ %l\ /\ %L\ (%3p%%)\         " line no. and pct

" Vundle plugin
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()

" let Vundle manage Vundle, required
Plugin 'Vundlevim/Vundle.vim'

" Add plugins 
Plugin 'scrooloose/nerdtree'
Plugin 'itchyny/lightline.vim'

call vundle#end() "required
" Vundle end


" show ruler
set ruler

" buffer become redundant when abandoned
set hid

" configure backspace
set backspace=eol,start,indent

" case-insensitive search
set ignorecase

" smart case when searching
set smartcase

" highlight search results
set hlsearch

" search incrementally
set incsearch

" turn magic on for regex
set magic

" show matching brackets
set showmatch
" how many tenths of a second to blink when matching brackets
set mat=2

" no error bells
set noerrorbells

" enable syntax highlighting
syntax enable

" set utf8 as standard encoding
set encoding=utf8

" turn backups and swapfiles off
set nobackup
set nowb
set noswapfile

" use spaces instead of tabs
set expandtab

" smart tabs
set smarttab

" 1 tab==4spaces
set shiftwidth=4
set tabstop=4

" linebreak on 500chrs
set lbr
set tw=500

set ai "auto indent
set si "smart indent
set wrap "wrap lines

" set hybrid line numbering
set number relativenumber

" switch dir to current file dir
set autochdir

" highlight cursorline
set cursorline

" set long history and undo levels
set history=700
set undolevels=700

" set clipboard to system
set clipboard=unnamed

