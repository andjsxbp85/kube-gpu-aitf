# AWS Kube Untuk Training Model LLM

Kebutuhan project ini (draf - temporary):

- 3 pod Jupyter statis
- tiap pod memakai 1 GPU
- tiap pod bisa diakses publik dari browser tanpa `port-forward`
- menggunakan gpu paling rendah -> instance type "g4dn.xlarge" (GPU 16GB) -> Nantinya ke A100

## Arsitektur yang Dipakai

Alur yang dipilih untuk draft ini:

1. Terraform membuat VPC dan EKS.
2. EKS memakai 3 node GPU.
3. NVIDIA device plugin di-install ke cluster.
4. Jupyter dijalankan sebagai `StatefulSet` 3 replika.
5. Tiap pod diekspos dengan `Service` bertipe `LoadBalancer`.

Hasil akhirnya (sementara 3, expected 8):

- `jupyter-0` -> 1 link publik
- `jupyter-1` -> 1 link publik
- `jupyter-2` -> 1 link publik

Pendekatan ini sengaja dipilih agar:

- nama pod stabil
- mapping pod ke endpoint publik jelas
- pengguna eksternal tidak perlu `kubectl` -> bisa buka lewat browser langsung, tanpa harus mendapatkan kube config
- tidak perlu `port-forward` -> bisa buka lewat browser langsung

## File Penting

- [main.tf](./main.tf)
untuk VPC, EKS, dan node GPU
- [jupyter.yml](./jupyter.yml)
  untuk `StatefulSet` Jupyter dan 3 public `LoadBalancer`
- [Dockerfile.md](./Dockerfile)
  untuk melakukan build images

## Pilihan Instance GPU Uji Coba

Node group saat ini diarahkan ke:

- `g4dn.xlarge`

Catatan:

- Jika kapasitas `g4dn.xlarge` sulit didapat di AZ tertentu, fallback paling dekat biasanya `g5.xlarge`.
- Karena targetnya 3 pod dan tiap pod meminta 1 GPU, maka secara praktis dibutuhkan 3 node single-GPU.

## Urutan Eksekusi

### 1. Provision infra

```bash
terraform init
terraform plan
terraform apply
```

### 2. Hubungkan `kubectl` ke cluster EKS

Contoh umum:

```bash
aws eks update-kubeconfig --region us-east-1 --name eks-anjas
```

### 3. Install NVIDIA device plugin

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml
```

### 4. Verifikasi node dan resource GPU

```bash
kubectl get nodes -L gpu,workload
kubectl describe node | grep -A5 Allocatable
```

Pastikan resource `nvidia.com/gpu` ada di node.

### 5. Deploy Jupyter

```bash
kubectl apply -f jupyter.yml
```

### 6. Ambil link publik tiap pod

```bash
kubectl get svc jupyter-0-public jupyter-1-public jupyter-2-public
```

AWS akan membuat 3 Network Load Balancer publik. Nilai `EXTERNAL-IP` atau hostname DNS dari ketiga service tadi

## Cara Kerja `jupyter.yml`

- 1 headless service untuk `StatefulSet`
- 1 `StatefulSet` dengan 3 replika
- 3 service publik:
  - `jupyter-0-public`
  - `jupyter-1-public`
  - `jupyter-2-public`

Setiap service publik memilih tepat 1 pod berdasarkan label:

- `statefulset.kubernetes.io/pod-name: jupyter-0`
- `statefulset.kubernetes.io/pod-name: jupyter-1`
- `statefulset.kubernetes.io/pod-name: jupyter-2`

## Keterbatasan Draft Saat Ini

Setup ini kondisi trialm, bukan production use (uji coba):

- token Jupyter masih statis -> ubah token secret jupyter
- belum ada persistence volume
- belum ada domain custom
- belum ada TLS/HTTPS

## Melihat Node EC2 EKS

Node EC2 worker yang dibentuk oleh EKS saat ini berada di private subnet, jadi umumnya:

- tidak punya public IP
- tidak bisa langsung di-SSH dari internet
- lebih aman diinspeksi lewat Kubernetes atau Session Manager

Untuk melihat pod berjalan di node mana:

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
```

Untuk melihat detail salah satu node:

```bash
kubectl describe node ip-10-0-1-37.ec2.internal
```

## Inspeksi Node Tanpa SSH

Cara paling praktis untuk melihat isi node adalah memakai debug pod:

```bash
kubectl debug node/ip-10-0-1-37.ec2.internal -it --image=ubuntu
```

Lalu masuk ke filesystem host:

```bash
chroot /host
```

Contoh perintah yang berguna:

```bash
ls -lah /dev/nvidia*
cat /proc/driver/nvidia/version
free -h
df -h
```

Catatan: EKS umumnya memakai `containerd`, bukan Docker sehingga itu `docker ps` sering tidak tersedia di node

Jika runtime tools ada, bisa coba:

```bash
crictl ps
ctr -n k8s.io containers list
```

## Verifikasi GPU yang Disarankan

### 1. Dari Kubernetes node

```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPUS:.status.allocatable.nvidia\\.com/gpu
```

Jika sehat, tiap node GPU akan menampilkan nilai `1`.

### 2. Dari pod Jupyter

```bash
kubectl exec -it jupyter-0 -- nvidia-smi
kubectl exec -it jupyter-0 -- python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Jika dua perintah ini berhasil, maka jalur GPU untuk workload Anda sudah benar.

## Rekomendasi Lanjutan

Setelah uji coba berhasil, langkah selanjutnya:

1. Tambah Route 53 record agar link lebih mudah dibagikan (if needed, optional)
2. Tambah HTTPS/TLS -> certbot + nginx
3. Simpan token per pod secara lebih aman, misalnya lewat `Secret`.
4. Tambah volume persisten bila hasil training atau notebook perlu disimpan.
5. Membatasi akses security group atau allowlist IP (if needed) -> hanya bisa lewat IP Universitas Brawijaya (misalnya)
