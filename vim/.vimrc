" .vimrc file with recommended configuration
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

" Vundle plugin
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()

" let Vundle manage Vundle, required
Plugin 'Vundlevim/Vundle.vim'

" Add plugins 
Plugin 'scrooloose/nerdtree'
Plugin 'itchyny/lightline.vim'
Plugin 'michaeljsmith/vim-indent-object'
Plugin 'junegunn/goyo.vim'
Plugin 'vim-scripts/indentpython.vim'

call vundle#end() "required
" Vundle end


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


" Filetype configurations

""""""""""""""""""""""""""""""
" => Python section
""""""""""""""""""""""""""""""
let python_highlight_all = 1
au FileType python syn keyword pythonDecorator True None False self

au BufNewFile,BufRead *.jinja set syntax=htmljinja
au BufNewFile,BufRead *.mako set ft=mako

au FileType python map <buffer> F :set foldmethod=indent<cr>

au FileType python inoremap <buffer> $r return 
au FileType python inoremap <buffer> $i import 
au FileType python inoremap <buffer> $p print 
au FileType python inoremap <buffer> $f # --- <esc>a
au FileType python map <buffer> <leader>1 /class 
au FileType python map <buffer> <leader>2 /def 
au FileType python map <buffer> <leader>C ?class 
au FileType python map <buffer> <leader>D ?def 

""""""""""""""""""""""""""""""
" => JavaScript section
"""""""""""""""""""""""""""""""
au FileType javascript call JavaScriptFold()
au FileType javascript setl fen
au FileType javascript setl nocindent

au FileType javascript,typescript imap <C-t> console.log();<esc>hi
au FileType javascript,typescript imap <C-a> alert();<esc>hi

au FileType javascript,typescript inoremap <buffer> $r return 
au FileType javascript,typescript inoremap <buffer> $f // --- PH<esc>FP2xi

function! JavaScriptFold() 
    setl foldmethod=syntax
    setl foldlevelstart=1
    syn region foldBraces start=/{/ end=/}/ transparent fold keepend extend

    function! FoldText()
        return substitute(getline(v:foldstart), '{.*', '{...}', '')
    endfunction
    setl foldtext=FoldText()
endfunction


""""""""""""""""""""""""""""""
" => CoffeeScript section
"""""""""""""""""""""""""""""""
function! CoffeeScriptFold()
    setl foldmethod=indent
    setl foldlevelstart=1
endfunction
au FileType coffee call CoffeeScriptFold()

au FileType gitcommit call setpos('.', [0, 1, 1, 0])


""""""""""""""""""""""""""""""
" => Twig section
""""""""""""""""""""""""""""""
autocmd BufRead *.twig set syntax=html filetype=html


""""""""""""""""""""""""""""""
" => Markdown
""""""""""""""""""""""""""""""
let vim_markdown_folding_disabled = 1


""""""""""""""""""""""""""""""
" => YAML
""""""""""""""""""""""""""""""
autocmd FileType yaml setlocal ts=2 sts=2 sw=2 expandtab
