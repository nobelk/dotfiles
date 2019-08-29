" Vimrc for Ubuntu console - compiled by nobel khandaker

" use vim mode instead of pure vi
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
set nojoinspaces
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

" move normally between wrapped lines
nmap j gj
nmap k gk

" syntax highlighting
syntax enable

" set editor specific settings 
set ruler
set autoindent
set number relativenumber
set wrap
set autochdir
set noerrorbells
set noswapfile autoread ttyfast visualbell

" set long history/undo
set history=900
set undolevels=900

" no introductory message
set shortmess+=atI

" Nerdtree config
map <C-o> :NERDTreeToggle<CR>
let g:NERDTreeDirArrowExpandable = '▸'
let g:NERDTreeDirArrowCollapsible = '▾'
let g:NERDTreeWinPos = "right"
let NERDTreeQuitOnOpen = 1

" lightline config
set laststatus=2
set noshowmode

" set file/command completion
set wildmenu
set wildmode=list:longest

" accurate bookmarking - jump to line + column of bookmark
nnoremap ` '
nnoremap ' `

" set terminal title
set title

" maintain context around cursor
set scrolloff=3

" let vim manage multiple buffers effectively
set hidden

" install vundle and plugins
filetype off
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
Plugin 'VundleVim/Vundle.vim'

" all plugins
Plugin 'itchyny/lightline.vim'
Plugin 'terryma/vim-multiple-cursors'
Plugin 'scrooloose/nerdtree'
Plugin 'flazz/vim-colorschemes' 
Plugin 'kien/ctrlp.vim'

call vundle#end()
filetype plugin indent on

" *** color/appearance lines needs to be after plugin lines ***
colorscheme atom

" set cursorline
set cursorline
highlight CursorLine cterm=NONE ctermbg=234
" *** end of color/appearance lines ***************************
