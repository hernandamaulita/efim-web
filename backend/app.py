from flask import Flask, request, jsonify 
import pandas as pd
import os
import numpy as np
from flask_cors import CORS
from efim import EFIM, jalankan_algoritma_efim  # Import kode EFIM yang telah dimodifikasi

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder uploads ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Variabel global untuk menyimpan jalur file dan berbagai status data
uploaded_path = None
raw_data = None  # Simpan data mentah asli
cleaned_data = None  # Data setelah pembersihan (tanpa utility)
processed_data = None  # Data setelah preprocessing lengkap (dengan utility)

def allowed_file(filename):
    allowed_extensions = ['csv', 'xlsx']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/upload', methods=['POST'])
def upload_file():
    global uploaded_path, raw_data
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Tidak ada file yang dikirim'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'File tidak valid. Harap unggah file CSV atau Excel.'}), 400
        
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        # Verifikasi file telah disimpan
        if not os.path.exists(filepath):
            return jsonify({'error': 'Gagal menyimpan file'}), 500
            
        uploaded_path = filepath
        
        # Segera baca dan simpan data mentah asli
        if filepath.endswith('.csv'):
            raw_data = pd.read_csv(filepath)
        elif filepath.endswith('.xlsx'):
            raw_data = pd.read_excel(filepath)
            
        return jsonify({'message': 'File berhasil diupload', 'file_path': filepath}), 200
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Upload error: {error_details}")
        return jsonify({'error': f'Gagal mengupload file: {str(e)}'}), 500

@app.route('/raw_preview', methods=['GET'])
def raw_preview():
    global uploaded_path, raw_data
    
    # Jika raw_data sudah tersedia, gunakan itu daripada membaca ulang file
    if raw_data is not None:
        print("Menggunakan data mentah yang sudah disimpan dalam memori")
        df = raw_data
    elif uploaded_path and os.path.exists(uploaded_path):
        try:
            print(f"Membaca preview file: {uploaded_path}")
            if uploaded_path.endswith('.csv'):
                df = pd.read_csv(uploaded_path)
            elif uploaded_path.endswith('.xlsx'):
                df = pd.read_excel(uploaded_path)
            else:
                return jsonify({'error': 'Format file tidak dikenali'}), 400
            # Update raw_data
            raw_data = df.copy()
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Preview error: {error_details}")
            return jsonify({'error': f'Gagal membaca file: {str(e)}', 'details': error_details}), 500
    else:
        return jsonify({'error': 'Belum ada file yang diupload atau file tidak ditemukan'}), 400

    n = int(request.args.get('n', 20))
    print(f"Berhasil membaca file. Jumlah baris: {len(df)}, Kolom: {df.columns.tolist()}")
    preview_data = df.head(n).to_dict(orient='records')
    return jsonify({
        'preview': preview_data,
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'column_names': list(df.columns)
    })

@app.route('/check_missing_and_duplicates', methods=['GET'])
def check_missing_and_duplicates():
    global uploaded_path, raw_data
    
    # Gunakan data yang sudah disimpan jika tersedia
    if raw_data is not None:
        df = raw_data.copy()
    elif uploaded_path and os.path.exists(uploaded_path):
        try:
            print(f"Memeriksa data untuk missing values dan duplikat: {uploaded_path}")
            if uploaded_path.endswith('.csv'):
                df = pd.read_csv(uploaded_path)
            elif uploaded_path.endswith('.xlsx'):
                df = pd.read_excel(uploaded_path)
            else:
                return jsonify({'error': 'Format file tidak dikenali'}), 400
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Check missing error: {error_details}")
            return jsonify({'error': f'Gagal memproses file: {str(e)}', 'details': error_details}), 500
    else:
        return jsonify({'error': 'Belum ada file yang diupload atau file tidak ditemukan'}), 400

    missing_values = df.isnull().sum().to_dict()
    missing_values = {k: (None if pd.isna(v) else int(v)) for k, v in missing_values.items()}

    num_duplicates = df.duplicated(keep=False).sum()
    num_unique_duplicates = df.duplicated().sum()

    print(f"Missing values: {missing_values}")
    print(f"Jumlah duplikat: {num_duplicates}")

    duplicate_groups = []
    if num_duplicates > 0:
        df_duplikat = df[df.duplicated(keep=False)].copy()
        df_duplikat['Duplicate_Group'] = df_duplikat.groupby(list(df.columns)).ngroup()
        duplicate_groups = df_duplikat.sort_values(by='Duplicate_Group').to_dict(orient='records')
        duplicate_groups = [
            {k: (None if pd.isna(v) else v) for k, v in group.items()} for group in duplicate_groups
        ]

    return jsonify({
        'missing_values': missing_values,
        'num_duplicates': int(num_duplicates),
        'num_unique_duplicates': int(num_unique_duplicates),
        'duplicate_groups': duplicate_groups
    })

@app.route('/preprocess', methods=['POST'])
def preprocess_data():
    global uploaded_path, raw_data, cleaned_data, processed_data
    
    # Gunakan data yang sudah disimpan jika tersedia
    if raw_data is not None:
        df = raw_data.copy()
    elif uploaded_path and os.path.exists(uploaded_path):
        try:
            print(f"Processing file: {uploaded_path}")
            if uploaded_path.endswith('.csv'):
                df = pd.read_csv(uploaded_path)
                print(f"Berhasil membaca file CSV. Ukuran data: {df.shape}")
            elif uploaded_path.endswith('.xlsx'):
                df = pd.read_excel(uploaded_path)
                print(f"Berhasil membaca file Excel. Ukuran data: {df.shape}")
            else:
                return jsonify({'error': 'Format file tidak dikenali'}), 400
            
            # Simpan data mentah asli
            raw_data = df.copy()
        except Exception as e:
            print(f"ERROR SAAT MEMBACA FILE: {str(e)}")
            return jsonify({'error': f'Gagal membaca file: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Belum ada file yang diupload atau file tidak ditemukan'}), 400

    try:
        print("============ MULAI DEBUGGING PREPROCESS ============")
        
        # Langkah 2: Periksa kolom yang ada
        print(f"Kolom dalam file: {df.columns.tolist()}")
        print(f"Tipe data per kolom: {df.dtypes.to_dict()}")
        print(f"Jumlah nilai NULL per kolom: {df.isnull().sum().to_dict()}")
        
        # Langkah 3: Standarisasi nama kolom
        df.columns = [col.upper().strip().replace(' ', '_') for col in df.columns]
        print(f"Kolom setelah standarisasi: {df.columns.tolist()}")
        
        # Langkah 4: Hapus baris kosong
        rows_before = len(df)
        df.dropna(how='all', inplace=True)
        print(f"Baris setelah hapus kosong: {len(df)} (dihapus {rows_before - len(df)})")

        # Langkah 5: Hapus kolom dengan banyak nilai kosong
        threshold = 0.5
        missing_fraction = df.isnull().mean()
        cols_to_drop = missing_fraction[missing_fraction > threshold].index.tolist()
        if cols_to_drop:
            print(f"Menghapus kolom dengan banyak nilai kosong: {cols_to_drop}")
            df.drop(columns=cols_to_drop, inplace=True)

        # Langkah 6: Hapus baris dengan nilai NaN dan duplikat
        rows_before = len(df)
        df.dropna(inplace=True)
        print(f"Baris setelah hapus NaN: {len(df)} (dihapus {rows_before - len(df)})")
        
        rows_before = len(df)
        df.drop_duplicates(inplace=True)
        print(f"Baris setelah hapus duplikat: {len(df)} (dihapus {rows_before - len(df)})")

        # Langkah 7: Konversi kolom TANGGAL
        if 'TANGGAL' in df.columns:
            print(f"Format nilai di kolom TANGGAL sebelum konversi: {df['TANGGAL'].head().tolist()}")
            # Simpan data asli sebelum konversi
            original_dates = df['TANGGAL'].copy()
            df['TANGGAL'] = pd.to_datetime(df['TANGGAL'], errors='coerce')
             # Identifikasi baris dengan tanggal tidak valid (NaT)
            invalid_mask = df['TANGGAL'].isna()
             # Tampilkan jumlah tanggal tidak valid
            print(f"Jumlah tanggal tidak valid: {invalid_mask.sum()}")
             # Tetapkan tanggal default untuk nilai tidak valid (misal: 2 juni 2010)
            default_date = pd.Timestamp('2010-06-02')
            df.loc[invalid_mask, 'TANGGAL'] = default_date
            print(f"Format nilai di kolom TANGGAL setelah konversi: {df['TANGGAL'].head().tolist()}")
            print(f"Nilai yang diubah menjadi tanggal default: {invalid_mask.sum()}")

        # Langkah 8: Hapus kolom yang tidak diperlukan
        columns_to_drop = ['NOMORREF', 'SATUAN']
        dropped = []
        for col in columns_to_drop:
            if col in df.columns:
                df.drop(col, axis=1, inplace=True)
                dropped.append(col)
        if dropped:
            print(f"Kolom yang dihapus: {dropped}")

        # Simpan data yang sudah dibersihkan tetapi belum ditambah kolom UTILITY
        df_cleaned = df.copy()
        cleaned_data = df_cleaned.copy()  # Simpan data setelah pembersihan
        print(f"Kolom setelah cleaning: {df_cleaned.columns.tolist()}")
        print(f"Ukuran data setelah cleaning: {df_cleaned.shape}")

        # Preview data setelah pembersihan (tanpa tambahan kolom utility)
        preview_cleaned = df_cleaned.copy()
        if 'TANGGAL' in preview_cleaned.columns and pd.api.types.is_datetime64_any_dtype(preview_cleaned['TANGGAL']):
            preview_cleaned['TANGGAL'] = preview_cleaned['TANGGAL'].dt.strftime('%Y-%m-%d')

        # Langkah 9: Tangani outlier
        df_numeric = df_cleaned.select_dtypes(include=['number'])
        if 'ID_PENJUALAN' in df_numeric.columns:
            df_numeric = df_numeric.drop(columns=['ID_PENJUALAN'])
            
        if not df_numeric.empty:
            print(f"Kolom numerik untuk deteksi outlier: {df_numeric.columns.tolist()}")
            Q1 = df_numeric.quantile(0.25)
            Q3 = df_numeric.quantile(0.75)
            IQR = Q3 - Q1
            
            print("Batas outlier:")
            for col in df_numeric.columns:
                lower_bound = Q1[col] - 1.5 * IQR[col]
                upper_bound = Q3[col] + 1.5 * IQR[col]
                print(f"  - {col}: [{lower_bound}, {upper_bound}]")
            
            filter_outlier = ~((df_numeric < (Q1 - 1.5 * IQR)) | (df_numeric > (Q3 + 1.5 * IQR))).any(axis=1)
            df_outlier_removed = df_cleaned[filter_outlier]
            print(f"Baris setelah penghapusan outlier: {len(df_outlier_removed)} (dihapus {len(df_cleaned) - len(df_outlier_removed)})")
        else:
            print("Tidak ada kolom numerik untuk deteksi outlier")
            df_outlier_removed = df_cleaned

        # Langkah 10: Cek dan tambahkan kolom yang diperlukan
        print("Validasi kolom yang diperlukan")
        required_cols = ['ID_PENJUALAN', 'KODE_BARANG', 'NAMA_BARANG', 'QTY', 'HARGASATUAN', 'TANGGAL']
        
        for col in required_cols:
            if col not in df_outlier_removed.columns:
                print(f"Kolom {col} tidak ditemukan - membuat kolom dengan nilai default")
                if col == 'ID_PENJUALAN':
                    df_outlier_removed[col] = range(1, len(df_outlier_removed) + 1)
                elif col == 'QTY':
                    df_outlier_removed[col] = 1
                elif col == 'HARGASATUAN':
                    df_outlier_removed[col] = 0
                elif col == 'TANGGAL':
                    df_outlier_removed[col] = pd.Timestamp.now()
                else:
                    df_outlier_removed[col] = "Data Tidak Tersedia"

        # BUAT COPY DATA SETELAH OUTLIER REMOVAL TAPI SEBELUM TAMBAH UTILITY
        df_before_utility = df_outlier_removed.copy()
        
        # Pastikan format tanggal konsisten untuk preview df_before_utility
        if 'TANGGAL' in df_before_utility.columns and pd.api.types.is_datetime64_any_dtype(df_before_utility['TANGGAL']):
            df_before_utility['TANGGAL'] = df_before_utility['TANGGAL'].dt.strftime('%Y-%m-%d')

        # Langkah 11: Tambahkan/Update UTILITY
        if all(col in df_outlier_removed.columns for col in ['QTY', 'HARGASATUAN']):
            # Buat kolom UTILITY baru
            df_outlier_removed['UTILITY'] = df_outlier_removed['QTY'] * df_outlier_removed['HARGASATUAN']
            print("Kolom UTILITY telah ditambahkan/diperbarui")
        else:
            df_outlier_removed['UTILITY'] = 0
            print("Dibuat kolom UTILITY dengan nilai 0")

        # Simpan data setelah preprocessing lengkap (dengan utility)
        processed_data = df_outlier_removed.copy()
        
        # Buat versi yang dapat ditampilkan untuk preview
        preview_df = processed_data.copy()
        if 'TANGGAL' in preview_df.columns and pd.api.types.is_datetime64_any_dtype(preview_df['TANGGAL']):
            preview_df['TANGGAL'] = preview_df['TANGGAL'].dt.strftime('%Y-%m-%d')

        # Langkah 12: Groupby untuk mendapatkan nilai agregat
        print("Melakukan operasi groupby")
        # Pastikan kolom 'UTILITY' ada dalam df_outlier_removed sebelum groupby
        if 'UTILITY' not in df_outlier_removed.columns:
            print("PERINGATAN: Kolom UTILITY tidak ditemukan sebelum groupby")
            # Cek kolom apa saja yang ada
            print(f"Kolom yang tersedia: {df_outlier_removed.columns.tolist()}")
        
        grouped = df_outlier_removed.groupby('ID_PENJUALAN').agg({
            'KODE_BARANG': lambda x: list(x.astype(str)),
            'NAMA_BARANG': lambda x: list(x.astype(str)),
            'QTY': lambda x: list(x),
            'HARGASATUAN': lambda x: list(x),
            'UTILITY': lambda x: list(x),
            'TANGGAL': lambda x: list(x)
        }).reset_index()
        print(f"Berhasil melakukan groupby, jumlah grup: {len(grouped)}")

        # Langkah 13: Simpan hasil preprocessing
        print("Menyimpan hasil preprocessing")
        preprocessed_path = os.path.join(app.config['UPLOAD_FOLDER'], 'preprocessed_data.csv')
        processed_data.to_csv(preprocessed_path, index=False)
        
        # Verifikasi file telah disimpan
        if os.path.exists(preprocessed_path):
            print(f"File preprocessed berhasil disimpan: {preprocessed_path}")
        else:
            print(f"Error: Gagal menyimpan file preprocessed: {preprocessed_path}")
            return jsonify({'error': 'Gagal menyimpan file hasil preprocessing'}), 500

        print("============ SELESAI DEBUGGING PREPROCESS ============")
        
        # Periksa kolom sebelum menjalankan EFIM
        print(f"Kolom dalam data processed_data sebelum EFIM: {processed_data.columns.tolist()}")
        
        # Jalankan EFIM secara otomatis setelah preprocessing
        min_util = request.json.get('min_util', 700000)  # Default nilai min_util jika tidak disediakan
        threshold = request.json.get('threshold', 700000)
        try:
            efim_result = run_efim(processed_data, threshold)
            print(f"EFIM berhasil dijalankan secara otomatis dengan min_util: {threshold}")
            
            # Gabungkan hasil preprocessing dan EFIM
            return jsonify({
                'after_cleaning': {
                    'preview': preview_cleaned.head(20).to_dict(orient='records'),
                    'total_rows': len(df_cleaned),
                    'total_columns': len(df_cleaned.columns),
                    'column_names': list(df_cleaned.columns)
                },
                'after_outlier_removal': {
                    'preview': df_before_utility.head(20).to_dict(orient='records'),
                    'total_rows': len(df_before_utility),
                    'total_columns': len(df_before_utility.columns),
                    'column_names': list(df_before_utility.columns)
                },
                'with_utility': {
                    'preview': preview_df.head(20).to_dict(orient='records'),
                    'total_rows': len(processed_data),
                    'total_columns': len(processed_data.columns),
                    'column_names': list(processed_data.columns)
                },
                'grouped_data': grouped.to_dict(orient='records'),
                'efim_result': efim_result
            })
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR SAAT MENJALANKAN EFIM OTOMATIS: {error_details}")
            
            # Jika EFIM gagal, tetap kembalikan hasil preprocessing
            return jsonify({
                'after_cleaning': {
                    'preview': preview_cleaned.head(20).to_dict(orient='records'),
                    'total_rows': len(df_cleaned),
                    'total_columns': len(df_cleaned.columns),
                    'column_names': list(df_cleaned.columns)
                },
                'after_outlier_removal': {
                    'preview': df_before_utility.head(20).to_dict(orient='records'),
                    'total_rows': len(df_before_utility),
                    'total_columns': len(df_before_utility.columns),
                    'column_names': list(df_before_utility.columns)
                },
                'with_utility': {
                    'preview': preview_df.head(20).to_dict(orient='records'),
                    'total_rows': len(processed_data),
                    'total_columns': len(processed_data.columns),
                    'column_names': list(processed_data.columns)
                },
                'grouped_data': grouped.to_dict(orient='records'),
                'efim_error': str(e)
            })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("============ ERROR UTAMA PADA PREPROCESS ============")
        print(error_details)
        print("============ AKHIR ERROR UTAMA ============")
        return jsonify({'error': f'Gagal melakukan preprocessing: {str(e)}', 'details': error_details}), 500

# Fungsi untuk menjalankan EFIM tanpa endpoint terpisah
def run_efim(df, threshold):
    try:
        print(f"Menjalankan EFIM dengan threshold: {threshold}")
        
        # Cek kolom yang diperlukan
        required_columns = {'ID_PENJUALAN', 'NAMA_BARANG', 'TANGGAL', 'KODE_BARANG', 'UTILITY'}
        missing_columns = required_columns - set(df.columns)
        
        if missing_columns:
            print(f"Kolom yang diperlukan tidak ditemukan: {missing_columns}")
            raise ValueError(f"File harus memiliki kolom: {required_columns}. Kolom yang hilang: {missing_columns}")
            
        # Ambil data transaksi
        transaksi_data = df[['ID_PENJUALAN', 'NAMA_BARANG', 'TANGGAL', 'KODE_BARANG', 'UTILITY']].copy()
        print(f"Data transaksi berhasil disiapkan, jumlah baris: {len(transaksi_data)}")

        # Buat mapping nama barang
        kode_nama_mapping = df[['KODE_BARANG', 'NAMA_BARANG']].drop_duplicates().set_index('KODE_BARANG')['NAMA_BARANG'].to_dict()

        # Hitung TWU per item
        twu_per_item = {}
        transaksi_grouped = transaksi_data.groupby('ID_PENJUALAN')
        for id_transaksi, group in transaksi_grouped:
            transaksi_utility = group['UTILITY'].sum()
            for item in group['KODE_BARANG'].unique():
                twu_per_item[item] = twu_per_item.get(item, 0) + transaksi_utility

        # Panggil algoritma EFIM
        hasil_itemset = jalankan_algoritma_efim(transaksi_data, threshold)
        print(f"EFIM berhasil dijalankan, jumlah itemset: {len(hasil_itemset)}")
        
        # Format hasil
        hasil_format = []
        for itemset, total_utility in hasil_itemset:
            itemset_list = list(itemset)
            nama_barang_list = [kode_nama_mapping.get(kode, f'Produk {kode}') for kode in itemset_list]

            rentang_waktu = 0
            terjual = 0
            # Hitung rentang waktu dan jumlah terjual
            for kode in itemset_list:
                kode_data = df[df['KODE_BARANG'] == kode]
                if not kode_data.empty:
                    if 'TANGGAL' in df.columns:
                        tanggal_data = pd.to_datetime(kode_data['TANGGAL'], errors='coerce')
                        valid_dates = tanggal_data.dropna()
                        if len(valid_dates) > 1:
                            date_range = (valid_dates.max() - valid_dates.min()).days
                            rentang_waktu = max(rentang_waktu, date_range)

                    if 'QTY' in df.columns:
                        terjual += kode_data['QTY'].sum()

            hasil_format.append({
                'kode_barang': itemset_list,
                'nama_barang': nama_barang_list,
                'total_utility': total_utility,
                'rentang_waktu': rentang_waktu,
                'total_terjual': terjual
            })
        total_twu = sum(twu_per_item.values())
        return {
            'message': 'EFIM berhasil dijalankan',
            'itemset_utilitas_tinggi': hasil_format,
            'threshold': threshold,
            'twu_per_item': twu_per_item,
            'twu': total_twu
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"EFIM processing error: {error_details}")
        raise Exception(f"Gagal menjalankan EFIM: {str(e)}")

# Tetap pertahankan endpoint terpisah untuk run_efim sebagai API
@app.route('/run_efim', methods=['POST'])
def run_efim_route():
    global processed_data, uploaded_path
    
    # Gunakan data yang sudah diproses jika tersedia
    if processed_data is not None:
        df = processed_data.copy()
        print("Menggunakan data yang sudah diproses dari memori")
    elif uploaded_path and os.path.exists(uploaded_path):
        try:
            print(f"Menjalankan EFIM untuk file: {uploaded_path}")
            if uploaded_path.endswith('.csv'):
                df = pd.read_csv(uploaded_path)
            elif uploaded_path.endswith('.xlsx'):
                df = pd.read_excel(uploaded_path)
            else:
                return jsonify({'error': 'Format file tidak dikenali'}), 400
        except Exception as e:
            return jsonify({'error': f'Gagal membaca file: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Belum ada file yang diupload atau data yang diproses'}), 400
    
    try:
        # Ambil parameter dari request
        data = request.get_json()
        min_util = data.get('min_util')
        
        if min_util is None:
            return jsonify({'error': 'Parameter min_util diperlukan'}), 400
            
        # Jika data sudah disediakan dalam request, gunakan itu
        if 'data' in data and data['data']:
            df = pd.DataFrame(data.get('data'))
        
        # Pastikan kolom UTILITY ada
        if 'UTILITY' not in df.columns and all(col in df.columns for col in ['QTY', 'HARGASATUAN']):
            df['UTILITY'] = df['QTY'] * df['HARGASATUAN']
        
        # Jalankan algoritma EFIM
        result = run_efim(df, min_util)
        return jsonify(result), 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"EFIM route error: {error_details}")
        return jsonify({'error': f'Gagal menjalankan EFIM: {str(e)}', 'details': error_details}), 500

# TAMBAHKAN ENDPOINT BARU UNTUK MELIHAT STATUS DATA BERBEDA
@app.route('/get_data_status', methods=['GET'])
def get_data_status():
    # Endpoint untuk mendapatkan informasi tentang status data
    global raw_data, cleaned_data, processed_data
    
    status = {
        'raw_data': raw_data is not None,
        'cleaned_data': cleaned_data is not None,
        'processed_data': processed_data is not None
    }
    
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True)