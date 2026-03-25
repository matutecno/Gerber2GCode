# Color palette and ttk Style configuration
COPPER_COLOR = '#DAA520'
PATH_COLOR = '#FF4444'
BG_DARK = '#1e1e1e'
BG_PANEL = '#2d2d2d'
FG_TEXT = '#e0e0e0'
ACCENT = '#4a9eff'

def apply(root):
    import tkinter.ttk as ttk
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background='#2d2d2d', foreground='#e0e0e0', fieldbackground='#3a3a3a')
    style.configure('TFrame', background='#2d2d2d')
    style.configure('TLabel', background='#2d2d2d', foreground='#e0e0e0')
    style.configure('TLabelframe', background='#2d2d2d', foreground='#aaaaaa')
    style.configure('TLabelframe.Label', background='#2d2d2d', foreground='#aaaaaa')
    style.configure('TEntry', fieldbackground='#3a3a3a', foreground='#e0e0e0', insertcolor='#e0e0e0')
    style.configure('TCombobox', fieldbackground='#3a3a3a', foreground='#e0e0e0')
    style.configure('TCheckbutton', background='#2d2d2d', foreground='#e0e0e0')
    style.configure('TButton', background='#3a3a3a', foreground='#e0e0e0')
    style.map('TButton', background=[('active', '#4a4a4a')])
    style.configure('Generate.TButton', background='#1a5c1a', foreground='white', font=('sans-serif', 10, 'bold'))
    style.map('Generate.TButton', background=[('active', '#267326'), ('disabled', '#333333')])
    style.configure('TScrollbar', background='#3a3a3a', troughcolor='#2d2d2d')
    style.configure('Treeview', background='#2d2d2d', foreground='#e0e0e0', fieldbackground='#2d2d2d')
    style.configure('Treeview.Heading', background='#3a3a3a', foreground='#aaaaaa')
    style.map('Treeview', background=[('selected', '#1a4a7a')])
