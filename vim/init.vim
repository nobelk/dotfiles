" init.vim file for neovim (nvim)
" Dr. Nobel Khandaker 

" use vim
set nocompatible
filetype off "required

" no intro message
set shortmess+=I

" set status bar at the bottom
set laststatus=2
set statusline+=\ %<%F\                           " file path
set statusline+=\ %=\ %l\ /\ %L\ (%3p%%)\         " line no. and pct


" Plug plugin manager
call plug#begin()
Plug 'sheerun/vim-polyglot'
Plug 'itchyny/lightline.vim'
Plug 'junegunn/goyo.vim'
Plug 'preservim/nerdtree'
Plug 'preservim/tagbar'
Plug 'vim-airline/vim-airline'
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'
call plug#end()


" With a map leader it's possible to do extra key combinations
" like <leader>w saves the current file
let mapleader = ","

" Fast saving
nmap <leader>w :w!<cr>


" show ruler
set ruler

" buffer become redundant when abandoned
set hid

" configure backspace
set backspace=eol,start,indent
set whichwrap+=<,>,h,l

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

" Add a bit of extra margin to the left
set foldcolumn=1


" NerdTree configurations
let NERDTreeShowHidden=0
let NERDTreeIgnore = ['\.pyc$', '__pycache__']
let g:NERDTreeWinSize=30
nnoremap <leader>n :NERDTreeFocus<CR>
nnoremap <C-n> :NERDTree<CR>
nnoremap <C-t> :NERDTreeToggle<CR>
nnoremap <C-f> :NERDTreeFind<CR>

" Spell checking
map <leader>ss :setlocal spell!<cr>

" Disable scrollbars (real hackers don't use scrollbars for navigation!)
set guioptions-=r
set guioptions-=R
set guioptions-=l
set guioptions-=L
