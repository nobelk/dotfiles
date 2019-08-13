" Vim only
set nocompatible

" display settings
set encoding=utf-8
set ruler
set showmatch
set showmode

" write settings
set confirm
set fileencoding=utf-8
set nobackup
set nowritebackup

" edit settings
set backspace=indent,eol,start
set bs=2
set expandtab
set shiftwidth=4
set softtabstop=4
set tabstop=4
set textwidth=80

" search settings
set hlsearch
set ignorecase
set incsearch
set smartcase

" center view on the search result
noremap n nzz
noremap N Nzz

" syntax highlighting
syntax enable

" set editor specific settings
set autoindent
set number
set number relativenumber
set ruler
set wrap
set autochdir
set cursorline
set noerrorbells
set noswapfile autoread ttyfast visualbell

" set long history and undo levels
set history=999
set undolevels=999

" no introductory message
set shortmess+=I

" install vundle and plugins
filetype off
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
Plugin 'VundleVim/Vundle.vim'

" add plugins here
Plugin 'atom/fuzzy-finder'
Plugin 'itchyny/lightline.vim'
Plugin 'terryma/vim-multiple-cursors'
Plugin 'scrooloose/nerdtree'

call vundle#end()

" Post plugin install configurations
filetype plugin indent on
"  Nerdtree
map <C-o> :NERDTreeToggle<CR>
let g:NERDTreeDirArrowExpandable = '+'
let g:NERDTreeDirArrowCollapsible = '~'

" lightline
set laststatus=2
set noshowmode
