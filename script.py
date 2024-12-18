import os
import sys
import time
import concurrent.futures
from pathlib import Path
from tqdm import tqdm
from PIL import Image
from pillow_heif import register_heif_opener
from wand.image import Image as WandImage

register_heif_opener()

def convert_heic_to_png(input_path, output_path):
    try:
        with Image.open(input_path) as img:
            img.save(output_path, 'PNG', optimize=True)
        return True
    except Exception as e:
        print(f"Erro ao converter {input_path}: {str(e)}")
        return False

def convert_cr2_to_png(input_path, output_path):
    try:
        with WandImage(filename=input_path) as img:
            img.format = 'png'
            img.compression_quality = 90
            if img.alpha_channel:
                img.alpha_channel = 'remove'
            img.save(filename=output_path)
        return True
    except Exception as e:
        print(f"Erro ao converter {input_path}: {str(e)}")
        return False

def optimize_png(input_path, output_path, max_size_mb=15):
    try:
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            max_dimension = 4000
            w, h = img.size
            if w > max_dimension or h > max_dimension:
                if w > h:
                    new_w = max_dimension
                    new_h = int(h * (max_dimension / w))
                else:
                    new_h = max_dimension
                    new_w = int(w * (max_dimension / h))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            quality = 90
            while True:
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                if size_mb <= max_size_mb or quality < 30:
                    return True, size_mb
                quality -= 5
    except Exception as e:
        print(f"Erro ao otimizar {input_path}: {str(e)}")
        return False, 0

def get_files_for_conversion(input_dir, ctype):
    exts = ['.heic', '.HEIC', '.heif', '.HEIF'] if ctype == 'HEIC' else ['.cr2', '.CR2']
    files = []
    for ext in exts:
        files.extend(list(Path(input_dir).glob(f'**/*{ext}')))
    return files

def process_conversion(files, input_dir, output_dir, func, max_workers):
    tasks = []
    for f in files:
        rel = f.relative_to(input_dir)
        out = Path(output_dir) / rel.with_suffix('.png')
        out.parent.mkdir(parents=True, exist_ok=True)
        tasks.append((str(f), str(out)))
    
    start = time.time()
    success, fail = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(func, i, o): (i, o) for i, o in tasks}
        with tqdm(total=len(tasks), desc="Convertendo imagens", unit="img") as pbar:
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    success += 1
                else:
                    fail += 1
                elapsed = time.time() - start
                pbar.set_postfix_str(f"Sucesso: {success}, Falhas: {fail}, Tempo: {elapsed:.2f}s")
                pbar.update(1)
    print("\nConversão concluída!")
    print(f"Convertidas com sucesso: {success}")
    print(f"Falhas: {fail}")

def process_optimization(input_dir, output_dir, max_workers, max_size_mb):
    png_files = list(Path(input_dir).glob('**/*.png'))
    if not png_files:
        print("Nenhum arquivo PNG encontrado para otimização.")
        return
    print(f"\nEncontrados {len(png_files)} arquivos PNG para otimização.")
    tasks = []
    total_original_size = 0
    for p in png_files:
        rel = p.relative_to(input_dir)
        out = Path(output_dir) / rel.with_suffix('.jpg')
        out.parent.mkdir(parents=True, exist_ok=True)
        tasks.append((str(p), str(out)))
        total_original_size += os.path.getsize(p) / (1024 * 1024)
    
    start = time.time()
    success, fail = 0, 0
    total_optimized_size = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(optimize_png, i, o, max_size_mb): (i, o) for i, o in tasks}
        with tqdm(total=len(tasks), desc="Otimizando imagens", unit="img") as pbar:
            for future in concurrent.futures.as_completed(futures):
                ok, size_mb = future.result()
                if ok:
                    success += 1
                    total_optimized_size += size_mb
                else:
                    fail += 1
                pbar.update(1)
    elapsed = time.time() - start
    print("\nOtimização concluída!")
    print(f"Convertidas com sucesso: {success}")
    print(f"Falhas: {fail}")
    print(f"Tamanho original: {total_original_size:.2f} MB")
    print(f"Tamanho otimizado: {total_optimized_size:.2f} MB")
    if total_original_size > 0:
        print(f"Redução: {((total_original_size - total_optimized_size) / total_original_size * 100):.2f}%")
    print(f"Tempo otimização: {elapsed:.2f}s")

if __name__ == "__main__":
    # Tipo
    while True:
        ctype = input("Digite o tipo de conversão (HEIC ou CR2): ")
        if ctype.upper() in ['HEIC', 'CR2']:
            ctype = ctype.upper()
            break
        print("Tipo inválido.")
    
    # Origem
    while True:
        input_dir = input("Caminho de origem: ")
        if Path(input_dir).exists():
            break
        print("Caminho inválido.")
    
    # Destino conversão
    while True:
        output_dir = input("Caminho de destino para conversão: ")
        if Path(output_dir).parent.exists():
            break
        print("Caminho inválido.")
    
    files = get_files_for_conversion(input_dir, ctype)
    if not files:
        print(f"Nenhum arquivo {ctype} encontrado.")
        sys.exit()

    print(f"Encontrados {len(files)} arquivos {ctype}")

    cpu_threads = os.cpu_count() or 4
    thread_options = list(range(2, cpu_threads+1, 2))
    print(f"\nEste computador possui {cpu_threads} threads. Opções: {thread_options}")
    while True:
        try:
            chosen_threads = int(input("Escolha o número de threads: "))
            if chosen_threads in thread_options:
                break
            print(f"Opção inválida. Escolha entre {thread_options}.")
        except ValueError:
            print(f"Opção inválida. Escolha entre {thread_options}.")

    avg_time = 0.5
    estimated = (len(files) * avg_time) / chosen_threads
    print(f"\nEstimativa de tempo de conversão: ~{estimated:.2f}s (pode variar)")

    print("\nConfirmação:")
    print(f"Tipo: {ctype}")
    print(f"Origem: {input_dir}")
    print(f"Destino conversão: {output_dir}")
    print(f"Threads: {chosen_threads}")
    confirm = input("Prosseguir? (S/N): ").upper()
    if confirm != 'S':
        print("Conversão cancelada.")
        sys.exit()

    start_total = time.time()
    func = convert_heic_to_png if ctype == 'HEIC' else convert_cr2_to_png
    process_conversion(files, input_dir, output_dir, func, chosen_threads)
    conv_time = time.time() - start_total

    # Pergunta otimização
    optimize_choice = input("\nDeseja otimizar as imagens convertidas? (S/N): ").upper()
    if optimize_choice == 'S':
        while True:
            output_dir_opt = input("Caminho de destino para otimização (JPEG): ")
            if Path(output_dir_opt).parent.exists():
                break
            print("Caminho inválido.")
        
        max_mb = 15
        try:
            val = input("Tamanho máximo em MB (padrão 15): ")
            if val.strip():
                max_mb = int(val)
        except:
            pass

        start_opt = time.time()
        process_optimization(output_dir, output_dir_opt, chosen_threads, max_mb)
        opt_time = time.time() - start_opt

        total_time = time.time() - start_total
        print(f"\nTempo total (conversão+otimização): {total_time:.2f}s")
    else:
        print(f"\nTempo total (apenas conversão): {conv_time:.2f}s")
