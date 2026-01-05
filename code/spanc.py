import dash
from dash import dcc, html, dash_table, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
import math
import io
import base64

app = dash.Dash(__name__)

# --- STİL AYARLARI ---
KUTU_STIL = {
    'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '15px',
    'boxShadow': '0 4px 10px rgba(0,0,0,0.1)', 'marginBottom': '20px'
}

app.layout = html.Div(style={'backgroundColor': '#f0f2f5', 'padding': '30px', 'fontFamily': 'Segoe UI'}, children=[
    html.H1("🏥 Spanç Operasyonel Verimlilik & Kapasite Terminali", style={'textAlign': 'center', 'color': '#1a3e59', 'fontWeight': 'bold'}),
    
    html.Div(style={'display': 'flex', 'gap': '20px'}, children=[
        # --- SOL PANEL: VERİ GİRİŞİ ---
        html.Div(style={'width': '25%', **KUTU_STIL}, children=[
            html.H3("📝 Veri Yönetimi"),
            html.Label("Ürün Türü:"),
            dcc.Dropdown(id='u-ad', options=[{'label': i, 'value': i} for i in ["10x10 Spanç (10'lu)", "10x10 Spanç (20'li)"]], value="10x10 Spanç (10'lu)"),
            
            html.Br(),
            html.Label("Haftalık Talep:"),
            dcc.Input(id='h-t', type='number', value=25000, style={'width': '100%', 'padding': '8px'}),
            
            html.Br(),
            html.Label("Haftalık Üretim:"),
            dcc.Input(id='h-u', type='number', value=25000, style={'width': '100%', 'padding': '8px'}),
            
            html.Br(),
            html.Label("Haftalık Sevkiyat:"),
            dcc.Input(id='h-s', type='number', value=24000, style={'width': '100%', 'padding': '8px'}),

            html.Br(),
            html.Label("Büyük Paket İçi Adet:"),
            dcc.Input(id='bp-i', type='number', value=20, style={'width': '100%', 'padding': '8px'}),

            html.Br(),
            html.Label("Tesis Toplam Raf Sayısı:"),
            dcc.Input(id='raf-s', type='number', value=60, style={'width': '100%', 'padding': '8px'}),

            html.Br(),
            html.Label("Personel İş Süresi (Sn/Paket):"),
            dcc.Input(id='is-sure', type='number', value=10, style={'width': '100%', 'padding': '8px'}),

            html.Br(),
            html.Label("Otoklav Kapasitesi (BP):"),
            dcc.Input(id='o-k', type='number', value=45, style={'width': '100%', 'padding': '8px'}),

            html.Hr(),
            html.Button('➕ YENİ ÜRÜN EKLE / GÜNCELLE', id='btn', n_clicks=0, style={'width': '100%', 'backgroundColor': '#1a3e59', 'color': 'white', 'padding': '12px', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer'}),
        ]),

        # --- SAĞ PANEL: GÖRSELLEŞTİRME ---
        html.Div(style={'width': '75%'}, children=[
            # ÜST METRİKLER (Anlık Güncellenen Özet)
            html.Div(id='ust-metrikler', style={'display': 'flex', 'gap': '15px'}),
            
            # ORTA KISIM: GRAFİK VE YANINDA MÜHENDİS TAVSİYESİ
            html.Div(style={'display': 'flex', 'gap': '15px'}, children=[
                html.Div(style={'width': '70%', **KUTU_STIL}, children=[
                    dcc.Graph(id='ana-grafik')
                ]),
                html.Div(id='muhendis-tavsiyesi', style={'width': '30%', **KUTU_STIL})
            ]),
            
            # ALT KISIM: TABLO VE EXCEL
            html.Div(style=KUTU_STIL, children=[
                html.H3("📑 Operasyonel Veri Tablosu"),
                dash_table.DataTable(
                    id='ana-tablo',
                    columns=[{"name": i, "id": i} for i in ["Ürün Tanımı", "Aylık Üretim", "Otoklav Döngüsü", "Personel İhtiyacı", "Raf Doluluğu (%)"]],
                    data=[],
                    style_header={'backgroundColor': '#D7E4BC', 'fontWeight': 'bold', 'border': '1px solid black'},
                    style_cell={'textAlign': 'center', 'border': '1px solid #ddd', 'padding': '10px'}
                ),
                html.Br(),
                html.A(html.Button("📥 EXCEL RAPORU ÇEK", style={'backgroundColor': '#28a745', 'color': 'white', 'padding': '12px', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold'}), 
                       id='excel-link', download="Spanc_Verimlilik_Raporu.xlsx", href="", target="_blank")
            ])
        ])
    ]),
    dcc.Store(id='hafiza', data=[])
])

# --- MANTIK ÜSSÜ (CALLBACK) ---
@app.callback(
    [Output('hafiza', 'data'), Output('ust-metrikler', 'children'), Output('ana-grafik', 'figure'), 
     Output('ana-tablo', 'data'), Output('muhendis-tavsiyesi', 'children'), Output('excel-link', 'href')],
    [Input('btn', 'n_clicks')],
    [State('u-ad', 'value'), State('h-t', 'value'), State('h-u', 'value'), State('h-s', 'value'),
     State('bp-i', 'value'), State('raf-s', 'value'), State('is-sure', 'value'), State('o-k', 'value'), State('hafiza', 'data')]
)
def operasyon_motoru(n, ad, ht, hu, hs, bpi, rafs, iss, ok, mevcut):
    # Aylık Çevrimler (Haftalık * 4)
    aylik_u = (hu or 0) * 4
    aylik_t = (ht or 0) * 4
    aylik_s = (hs or 0) * 4
    
    # Hesaplamalar
    gerekli_bp = math.ceil(aylik_u / (bpi or 1))
    dongu = math.ceil(gerekli_bp / (ok or 1))
    oto_ihtiyac = math.ceil(dongu / 220) # 220 döngü aylık limit
    
    # Personel: (Üretim * Süre) / (8 saat * 3600 sn * 22 gün)
    personel = round((aylik_u * (iss or 0)) / (8 * 3600 * 22), 2)
    
    # Raf Doluluğu (Üretim - Sevkiyat farkının rafa etkisi)
    net_stok_bp = (aylik_u - aylik_s) / (bpi or 1)
    raf_doluluk = round((net_stok_bp / (rafs or 1)) * 100, 1) if rafs else 0

    if n > 0:
        yeni = {
            "Ürün Tanımı": ad, "Aylık Üretim": aylik_u, "Aylık Talep": aylik_t,
            "Otoklav Döngüsü": dongu, "Otoklav İhtiyacı": oto_ihtiyac,
            "Personel İhtiyacı": personel, "Raf Doluluğu (%)": f"%{raf_doluluk}"
        }
        mevcut = [d for d in mevcut if d['Ürün Tanımı'] != ad]
        mevcut.append(yeni)

    df = pd.DataFrame(mevcut)
    if df.empty: return mevcut, [], {}, [], "", ""

    # 1. Metrikler (Üst Bölüm)
    metrikler = [
        html.Div(style={'flex': '1', **KUTU_STIL, 'textAlign': 'center', 'borderTop': '5px solid #007bff'}, children=[html.Small("Aylık Üretim"), html.H2(f"{df['Aylık Üretim'].sum():,}")]),
        html.Div(style={'flex': '1', **KUTU_STIL, 'textAlign': 'center', 'borderTop': '5px solid #28a745'}, children=[html.Small("Gerekli Personel"), html.H2(f"{round(df['Personel İhtiyacı'].sum(), 1)} Kişi")]),
        html.Div(style={'flex': '1', **KUTU_STIL, 'textAlign': 'center', 'borderTop': '5px solid #ffc107'}, children=[html.Small("Gerekli Otoklav"), html.H2(f"{df['Otoklav İhtiyacı'].sum()} Adet")])
    ]

    # 2. Grafik
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Üretim', x=df['Ürün Tanımı'], y=df['Aylık Üretim'], marker_color='#007bff'))
    fig.add_trace(go.Scatter(name='Talep Hedefi', x=df['Ürün Tanımı'], y=df['Aylık Talep'], mode='lines+markers', line=dict(color='red', width=4, dash='dash')))
    fig.update_layout(title="Üretim vs Talep Dengesi", template='plotly_white', height=500, margin=dict(l=20,r=20,t=40,b=20))

    # 3. Mühendis Tavsiyesi
    t_dongu = df['Otoklav Döngüsü'].sum()
    tavsiye = html.Div([
        html.H4("💡 Mühendislik Notu"),
        html.Div(style={'padding': '15px', 'backgroundColor': '#1a3e59', 'color': 'white', 'borderRadius': '10px'}, children=[
            html.P(f"Toplam Döngü: {t_dongu}"),
            html.B("DURUM: " + ("Kapasite Yeterli" if t_dongu <= 220 else "EK CİHAZ GEREKLİ!")),
            html.P(f"Toplam Raf Yükü: %{round(df['Aylık Üretim'].sum() / (bpi * rafs) * 100, 1) if rafs else 0}")
        ])
    ])

    # 4. Excel Rapor
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Verimlilik_Raporu')
        workbook = writer.book
        worksheet = writer.sheets['Verimlilik_Raporu']
        fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
        for i, col in enumerate(df.columns):
            worksheet.write(0, i, col, fmt)
            worksheet.set_column(i, i, 20)
    
    excel_data = base64.b64encode(buffer.getvalue()).decode()
    href = f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_data}"

    return mevcut, metrikler, fig, df.to_dict('records'), tavsiye, href

if __name__ == '__main__':
    app.run(debug=True)