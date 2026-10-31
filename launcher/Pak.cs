// Lector del directorio de un .pak de Angels Online (formato "OD"), igual que server/parche.py:
//   * los ultimos 22 bytes (EOCD) van con XOR (3*i - 91) desde el byte 4
//   * el directorio va comprimido con zlib, con su primer byte XOR 0x7A
//   * cada entrada: 46 bytes + nombre
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace AngelsLauncher
{
    static class Pak
    {
        public static List<string> Nombres(string ruta)
        {
            var salida = new List<string>();
            byte[] datos = File.ReadAllBytes(ruta);
            if (datos.Length < 22) return salida;
            byte[] eocd = new byte[22];
            Array.Copy(datos, datos.Length - 22, eocd, 0, 22);
            if (eocd[0] != (byte)'O' || eocd[1] != (byte)'D' || eocd[2] != 5 || eocd[3] != 6) return salida;
            for (int i = 4; i < 22; i++) eocd[i] ^= (byte)((3 * i - 91) & 0xFF);
            int comp = BitConverter.ToInt32(eocd, 4);
            int cdOff = BitConverter.ToInt32(eocd, 16);
            if (comp <= 2 || cdOff + 4 + comp > datos.Length) return salida;
            byte[] raw = new byte[comp];
            Array.Copy(datos, cdOff + 4, raw, 0, comp);
            raw[0] ^= 0x7A;
            byte[] cd;
            // zlib = 2 bytes de cabecera + deflate crudo (+ adler32 al final, que DeflateStream ignora)
            using (var entrada = new MemoryStream(raw, 2, raw.Length - 2))
            using (var inflar = new DeflateStream(entrada, CompressionMode.Decompress))
            using (var mem = new MemoryStream())
            {
                inflar.CopyTo(mem);
                cd = mem.ToArray();
            }
            int off = 0;
            while (off + 46 <= cd.Length)
            {
                int nl = BitConverter.ToUInt16(cd, off + 28);
                int xl = BitConverter.ToUInt16(cd, off + 30);
                int cl = BitConverter.ToUInt16(cd, off + 32);
                if (off + 46 + nl > cd.Length) break;
                salida.Add(Encoding.ASCII.GetString(cd, off + 46, nl).ToUpperInvariant().Replace('/', '\\'));
                off += 46 + nl + xl + cl;
            }
            return salida;
        }
    }
}
