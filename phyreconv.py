import io
import math
from pathlib import Path
from bitarray import bitarray
from bitarray import util as bitarray_util
import pyzorder

DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000
DDSD_DEPTH = 0x800000


DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_YUV = 0x200
DDPF_LUMINANCE = 0x20000

DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000

DDSFCC_DXT5 = 0x35545844 # DXT5
DDSFCC_DXT3 = 0x33545844 # DXT3
DDSFCC_DXT1 = 0x31545844 # DXT1
DDSFCC_BC5U = 0x55354342 # BC5U
DDSFCC_ATI2 = 0x32495441 # ATI2
DDSFCC_BC7 =  0x20374342 # BC7 
DDSFCC_DX10 = 0x30315844 # DX10

def getNullTermedString(byts, offs):
    data = byts[offs:]
    null = data.find(b'\x00')
    if data != -1:
        return data[:null].decode('utf-8')
    else:
        return data.decode('utf-8')

def getPow2(num):
    return int(math.log(num) / math.log(2))

def Morton(x, y, sx, sy):
    result = 0
    shift = 0
    while (sx + sy) != 0:
        if sx != 0:
            sx -= 1
            result |= (x & 1) << shift
            x >>= 1
            shift += 1
        if sy != 0:
            sy -= 1
            result |= (y & 1) << shift
            y >>= 1
            shift += 1
    return result


def Image_MortonOrder(src, dst, width, height, bytesPerPixel, flags, resv):
    if resv != 0:
        print("Image_MortonOrder: resv must be 0.")
        exit()
    widthPow2 = getPow2(width)
    heightPow2 = getPow2(height)
    srcOffset = 0
    calculatedSize = bytesPerPixel * height * width
    for y in range(0, height):
        for x in range(0, width):
            index = 0
            if (flags & 2) != 0:
                index = Morton(y, x, heightPow2, widthPow2)
            else:
                index = Morton(x, y, widthPow2, heightPow2)
            dstOffset = bytesPerPixel * index
            if srcOffset + bytesPerPixel <= calculatedSize and dstOffset + bytesPerPixel <= calculatedSize:
                v33 = srcOffset
                v34 = dstOffset
                if (flags & 1) != 0:
                    v33, v34 = v34, v33
                dst[v34:v34+bytesPerPixel] = src[v33:v33+bytesPerPixel]
                srcOffset += bytesPerPixel

def IsPixelFormatCompressed(pixelFormat):
    return pixelFormat == "ARGB8" # TODO: full impl

def GetsourceBytesPerPixelSetAndPixelSize(pixelFormat):
    pixelBlockSize = IsPixelFormatCompressed(pixelFormat) and 4 or 1
    return pixelBlockSize
    
class _tNamespaceHeader:
    def __init__(self, buf):
        assert buf.read(4) == b'\x01\x02\x03\x04'
        self.size = int.from_bytes(buf.read(4), 'big', signed=False)
        self.typeCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.classCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.classDataMemberCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.stringTableSize = int.from_bytes(buf.read(4), 'big', signed=False)
        self.defaultBufferCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.defaultBufferSize = int.from_bytes(buf.read(4), 'big', signed=False)


class _tInstanceDescriptor:
    SIZE = 9*4
    def __init__(self, buf):
        self.classId = int.from_bytes(buf.read(4), 'big', signed=False)
        self.count = int.from_bytes(buf.read(4), 'big', signed=False)
        self.size = int.from_bytes(buf.read(4), 'big', signed=False)
        self.objectSize = int.from_bytes(buf.read(4), 'big', signed=False)
        self.arraysSize = int.from_bytes(buf.read(4), 'big', signed=False)
        self.pointersInArraysCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.arrayFixupCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.pointerFixupCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.pointerArrayFixupCount = int.from_bytes(buf.read(4), 'big', signed=False)


class _tNamespaceClassDescriptor:
    def __init__(self, buf, stringTable):
        self.baseClassId = int.from_bytes(buf.read(4), 'big', signed=False)
        self.sizeAndAlign = int.from_bytes(buf.read(4), 'big', signed=False)
        self.nameOffset = int.from_bytes(buf.read(4), 'big', signed=False)
        self.name = getNullTermedString(stringTable, self.nameOffset)
        self.dataMemberCount = int.from_bytes(buf.read(4), 'big', signed=False)
        self.offsetFromParent = int.from_bytes(buf.read(4), 'big', signed=False)
        self.offsetToBase = int.from_bytes(buf.read(4), 'big', signed=False)
        self.offsetToBaseInAllocateBlock = int.from_bytes(buf.read(4), 'big', signed=False)
        self.flags = int.from_bytes(buf.read(4), 'big', signed=False)
        self.defaultBufferOffset = int.from_bytes(buf.read(4), 'big', signed=False)

class _tNamespaceDataMember:
    def __init__(self, buf, stringTable):
        self.nameOffset = int.from_bytes(buf.read(4), 'big', signed=False)
        self.name = getNullTermedString(stringTable, self.nameOffset)
        self.typeId = int.from_bytes(buf.read(4), 'big', signed=False)
        self.valueOffset = int.from_bytes(buf.read(4), 'big', signed=False)
        self.size = int.from_bytes(buf.read(4), 'big', signed=False)
        self.flags = int.from_bytes(buf.read(4), 'big', signed=False)
        self.fixedArraySize = int.from_bytes(buf.read(4), 'big', signed=False)

GCMHeader_size = 22*4
class _tGCMHeader:
    def __init__(self, phyreFile):
        self.m_phyreMarker = phyreFile.read(4)
        assert self.m_phyreMarker == b'PHYR'
        self.size = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.namespaceSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_platformID = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_instanceListCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_arrayFixupSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_arrayFixupCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_pointerFixupSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_pointerFixupCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_pointerArrayFixupSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_pointerArrayFixupCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_pointersInArraysCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_userFixupCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_userFixupDataSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_totalDataSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_headerClassInstanceCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_headerClassChildCount = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.m_physicsEngineID = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.indexBufferSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.vertexBufferSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.maxTextureBufferSize = int.from_bytes(phyreFile.read(4), 'big', signed=False)
        self.idk = int.from_bytes(phyreFile.read(4), 'big', signed=False)

def getInstances(phyreFile, instanceOffset, classes, stringTable, instanceCount):
    phyreFile.seek(instanceOffset, 0)
    start = 0
    instances = {}
    for i in range(0, instanceCount):
        instanceDescriptor = _tInstanceDescriptor(phyreFile)
        instanceDescriptor.start = start
        start += instanceDescriptor.size
        instances[classes[instanceDescriptor.classId - 1].name] = instanceDescriptor
    return instances

def getDataMember(phyreFile, dataOffset, instance, member):
    phyreFile.seek(dataOffset, 0)
    phyreFile.seek(instance.start, 1)
    phyreFile.seek(member.valueOffset, 1)
    return int.from_bytes(phyreFile.read(member.size), 'big', signed=False)

class _tTextureInfo:
    def __init__(self):
        self._format = 0
        self.memoryType = 0
        self.mipmapCount = 0
        self.maxMipmapLevel = 0
        self.textureFlags = 0
        self.width = 0
        self.height = 0
        self.textureFormat = ""
        self.fixupOffset = 0
        self.fixupDataOffset = 0
        self.textureInfoOffset = 0
        self.dataOffset = 0

class _tUserFixup:
    SIZE = 12
    def __init__(self):
        self.typeId = 0
        self.size = 0
        self.offset = 0
    def read(self, f):
        self.typeId = int.from_bytes(f.read(4), 'big', signed=False)
        self.size = int.from_bytes(f.read(4), 'big', signed=False)
        self.offset = int.from_bytes(f.read(4), 'big', signed=False)

PLATFORMID = 0x47434D00

def _getTextureInfo(header, instances, members, stringTable, phyreFile, dataOffset):
    textureInfo = _tTextureInfo()
    textureInfo.width = getDataMember(phyreFile, dataOffset, instances['PTexture2D'], members['m_width'])
    textureInfo.height = getDataMember(phyreFile, dataOffset, instances['PTexture2D'], members['m_height'])
    textureInfo.mipmapCount = getDataMember(phyreFile, dataOffset, instances['PTexture2D'], members['m_mipmapCount'])
    textureInfo.maxMipmapLevel = getDataMember(phyreFile, dataOffset, instances['PTexture2D'], members['m_maxMipLevel'])
    textureInfo.textureFlags = getDataMember(phyreFile, dataOffset, instances['PTexture2D'], members['m_textureFlags'])
    return textureInfo

def _getPhyreInfo(phyreFile, filesize):
    if filesize < GCMHeader_size:
        raise Exception("File too small to be dx11 platform type")
    phyreHeader = _tGCMHeader(phyreFile)
    
    if phyreHeader.m_platformID != PLATFORMID or phyreHeader.size != GCMHeader_size or filesize < 0 + phyreHeader.size + phyreHeader.namespaceSize:
        raise Exception("Size too small to fit namespace")
    
    namespaceBuffer = phyreFile.read(phyreHeader.namespaceSize)
    namespaceBufferIO = io.BytesIO(namespaceBuffer)
    
    namespaceHeader = _tNamespaceHeader(namespaceBufferIO)
    
    stringTableStart = namespaceHeader.size - namespaceHeader.stringTableSize - (namespaceHeader.defaultBufferCount * namespaceHeader.defaultBufferSize)
    stringTable = namespaceBuffer[stringTableStart:]
    
    typeDescriptors = []
    for i in range(0, namespaceHeader.typeCount):
        typeDescriptors.append(int.from_bytes(namespaceBufferIO.read(4), 'big', signed=False))
    
    classDescriptors = []
    for i in range(0, namespaceHeader.classCount):
        classDescriptors.append(_tNamespaceClassDescriptor(namespaceBufferIO, stringTable))

    memberDescriptors = {}
    for i in range(0, namespaceHeader.classDataMemberCount):
        dataMember = _tNamespaceDataMember(namespaceBufferIO, stringTable)
        memberDescriptors[dataMember.name] = dataMember
    
    instances = getInstances(phyreFile, 0 + phyreHeader.size + namespaceHeader.size, classDescriptors, stringTable, phyreHeader.m_instanceListCount)
    textureInfoStart = phyreFile.tell()
    textureInfo = _getTextureInfo(namespaceHeader, instances, memberDescriptors, stringTable, phyreFile, textureInfoStart)
    textureInfo.textureInfoOffset = textureInfoStart
    
    userFixupBuffer = bytearray(phyreHeader.m_userFixupDataSize)
    textureInfo.fixupDataOffset = 0 + phyreHeader.size + namespaceHeader.size + (phyreHeader.m_instanceListCount * _tInstanceDescriptor.SIZE) + phyreHeader.m_totalDataSize
    phyreFile.seek(textureInfo.fixupDataOffset, 0)
    userFixupBuffer = phyreFile.read(phyreHeader.m_userFixupDataSize)
    
    userFixup = _tUserFixup()
    textureInfo.fixupOffset = 0 + phyreHeader.size + namespaceHeader.size + (phyreHeader.m_instanceListCount *_tInstanceDescriptor.SIZE) + phyreHeader.m_totalDataSize + phyreHeader.m_userFixupDataSize
    phyreFile.seek(textureInfo.fixupOffset + _tUserFixup.SIZE, 0)
    userFixup.read(phyreFile)
    
    if userFixup.typeId >= namespaceHeader.typeCount or getNullTermedString(stringTable, typeDescriptors[userFixup.typeId]) != "PTextureFormatBase":
        raise Exception("Texture format not found")
    
    textureInfo.textureFormat = getNullTermedString(userFixupBuffer, userFixup.offset)
    
    dataOffset = 0 + phyreHeader.size + namespaceHeader.size + (phyreHeader.m_instanceListCount * _tInstanceDescriptor.SIZE) \
        + phyreHeader.m_totalDataSize \
        + phyreHeader.m_userFixupDataSize + (_tUserFixup.SIZE * phyreHeader.m_userFixupCount) \
        + phyreHeader.m_pointerArrayFixupSize + phyreHeader.m_pointerFixupSize + phyreHeader.m_arrayFixupSize
    
    textureInfo.dataOffset = dataOffset
    
    return textureInfo

class _tDDS_PIXELFORMAT:
    SIZE = 8*4
    def __init__(self):
        self.dwSize = _tDDS_PIXELFORMAT.SIZE
        self.dwFlags = DDPF_FOURCC
        self.dwFourCC = 0
        self.dwRGBBitCount = 32
        self.dwRBitMask = 0x000000FF
        self.dwGBitMask = 0x0000FF00
        self.dwBBitMask = 0x00FF0000
        self.dwABitMask = 0xFF000000
    def convertToBytes(self):
        result = b''
        for key, value in vars(self).items():
            if type(value) is int:
                result += value.to_bytes(4, 'little')
            elif type(value) is bytes:
                result += value
        return result

class _tDDS_HEADER:
    def __init__(self):
        self.magic = b'DDS '
        self.dwSize = 0
        self.dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
        self.dwHeight = 0
        self.dwWidth = 0
        self.dwPitchOrLinearSize = 0
        self.dwDepth = 1
        self.dwMipMapCount = 1
        self.dwReserved1 = b'\x00\x00\x00\x00' * 11
        self.ddspf = _tDDS_PIXELFORMAT()
        self.dwCaps = DDSCAPS_TEXTURE
        self.dwCaps2 = 0
        self.dwCaps3 = 0
        self.dwCaps4 = 0
        self.dwReserved2 = 0
    def convertToBytes(self):
        result = b''
        for key, value in vars(self).items():
            if type(value) is int:
                result += value.to_bytes(4, 'little')
            elif type(value) is bytes:
                result += value
            elif type(value) is _tDDS_PIXELFORMAT:
                result += value.convertToBytes()
        return result
        

def prepareDDSHeader(_format, width, height, mipmaps, useDX10):
    header = _tDDS_HEADER()
    header.dwWidth = width
    header.dwHeight = height
    header.dwMipMapCount = mipmaps + 1
    header.dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    
    if mipmaps > 0:
        header.dwFlags |= DDSD_MIPMAPCOUNT
        header.dwCaps = DDSCAPS_TEXTURE | DDSCAPS_MIPMAP | DDSCAPS_COMPLEX
    
    if _format == "BC7" and useDX10:
        header.ddspf.dwFlags = DDPF_FOURCC
        header.ddspf.dwFourCC = DDSFCC_DX10
        header.dwPitchOrLinearSize = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 16
    elif _format == "DXT5" or _format == "DXT3" or _format == "DXT1" or _format == "BC5" or _format == "BC7":
        header.ddspf.dwFlags = DDPF_FOURCC
        header.ddspf.dwRBitMask = 0
        header.ddspf.dwGBitMask = 0
        header.ddspf.dwBBitMask = 0
        header.ddspf.dwABitMask = 0
        header.dwPitchOrLinearSize = max(1, (width + 3) // 4) * max(1, (height + 3) // 4)
        match _format:
            case "DXT5":
                header.ddspf.dwFourCC = DDSFCC_DXT5
                header.dwPitchOrLinearSize *= 16
            case "DXT3":
                header.ddspf.dwFourCC = DDSFCC_DXT3
                header.dwPitchOrLinearSize *= 16
            case "DXT1":
                header.ddspf.dwFourCC = DDSFCC_DXT1
                header.dwPitchOrLinearSize *= 8
            case "BC5":
                header.ddspf.dwFourCC = DDSFCC_BC5U
                header.dwPitchOrLinearSize *= 16
            case "BC7":
                header.ddspf.dwFourCC = DDSFCC_BC7
                header.dwPitchOrLinearSize *= 16
    elif _format == "ARGB8":
        header.dwFlags |= DDSD_PITCH
        header.ddspf.dwFlags = DDPF_ALPHAPIXELS | DDPF_RGB
        header.ddspf.dwRGBBitCount = 32
        header.ddspf.dwRBitMask = 0x00FF0000
        header.ddspf.dwGBitMask = 0x0000FF00
        header.ddspf.dwBBitMask = 0x000000FF
        header.ddspf.dwABitMask = 0xFF000000
        header.dwPitchOrLinearSize = width * 4
    elif _format == "RGBA8":
        header.dwFlags |= DDSD_PITCH
        header.ddspf.dwFlags = DDPF_ALPHAPIXELS | DDPF_RGB
        header.ddspf.dwRGBBitCount = 32
        header.ddspf.dwRBitMask = 0x000000FF
        header.ddspf.dwGBitMask = 0x0000FF00
        header.ddspf.dwBBitMask = 0x00FF0000
        header.ddspf.dwABitMask = 0xFF000000
        header.dwPitchOrLinearSize = width * 4
    elif _format == "A8":
        header.dwFlags |= DDSD_PITCH
        header.ddspf.dwFlags = DDPF_ALPHA
        header.ddspf.dwRGBBitCount = 8
        header.ddspf.dwABitMask = 0xFF
        header.dwPitchOrLinearSize = width
    elif _format == "L8":
        header.dwFlags |= DDSD_PITCH
        header.ddspf.dwFlags = DDPF_LUMINANCE
        header.ddspf.dwRGBBitCount = 8
        header.ddspf.dwRBitMask = 0xFF
        header.dwPitchOrLinearSize = width
    else:
        raise Exception(f'Unsupported format: {_format}')
    
    return header

def write_reversed(data, f):
    f.write(data[::-1])

def convertPhyre2DDS(phyrePath, ddsPath):
    filesize = 0
    with open(phyrePath, 'rb') as phyreFile:
        filesize = len(phyreFile.read())
    with open(phyrePath, 'rb') as phyreFile:
        textureInfo = None
        try:
            textureInfo = _getPhyreInfo(phyreFile, filesize)
        except Exception as e:
            return
        
        if textureInfo.dataOffset >= filesize:
            raise Exception("There is no DDS data in the phyre file")
        
        useDX10 = (textureInfo.textureFormat == "BC7")
        ddsHeader = prepareDDSHeader(textureInfo.textureFormat, textureInfo.width, textureInfo.height, textureInfo.mipmapCount, useDX10)
        
        with open(ddsPath, 'wb+') as f:
            pass
        with open(ddsPath, 'ab+') as ddsFile:
            dataSize = filesize - textureInfo.dataOffset
            dataBuffer = None
            phyreFile.seek(textureInfo.dataOffset, 0)
            dataBuffer = bytearray(phyreFile.read(dataSize))
            
            rowPitch = 0
            if (ddsHeader.dwFlags & DDSD_PITCH) != 0:
                rowPitch = ddsHeader.dwPitchOrLinearSize
            elif (ddsHeader.dwFlags & DDSD_LINEARSIZE) != 0:
                rowPitch = ddsHeader.dwPitchOrLinearSize // ddsHeader.dwHeight
            
            if textureInfo.textureFormat != "ARGB8":
                if rowPitch > 0:
                    height = ddsHeader.dwHeight
                    rowBuffer = bytearray(rowPitch)
                    y = 0
                    while y < height//2:
                        topRow = y * rowPitch
                        bottomRow = (height - 1 - y) * rowPitch
                        rowBuffer[0:rowPitch] = dataBuffer[topRow:topRow+rowPitch]
                        dataBuffer[topRow:topRow+rowPitch] = dataBuffer[bottomRow:bottomRow+rowPitch]
                        dataBuffer[bottomRow:bottomRow+rowPitch] = rowBuffer[0:0+rowPitch]
                        y+=1
            
            if useDX10:
                dx10Header = _tDDS_HEADER_DXT10()
                dx10Header.dxgiFormat = DXGI_FORMAT_BC7_UNORM
                dx10Header.resourceDimension = 3
                dx10Header.arraySize = 1
                
                ddsFile.write(ddsHeader.convertToBytes())
                ddsFile.write(dx10Header.convertToBytes())
            else:
                ddsFile.write(ddsHeader.convertToBytes())
            match textureInfo.textureFormat:
                case "DXT1":
                    for i in range(0, len(dataBuffer)//8):
                        offs = i*8
                        color0 = dataBuffer[offs:offs+2]
                        color1 = dataBuffer[offs+2:offs+4]
                        codes = dataBuffer[offs+4:offs+8]
                        ddsFile.write(color0)
                        ddsFile.write(color1)
                        write_reversed(codes, ddsFile)
                case "DXT3":
                    for i in range(0, len(dataBuffer)//16):
                        offs = i*16
                        alpha_data = dataBuffer[offs:offs+8]
                        color0 = dataBuffer[offs+8:offs+10]
                        color1 = dataBuffer[offs+10:offs+12]
                        codes = dataBuffer[offs+12:offs+16]
                        ddsFile.write(alpha_data[6:8])
                        ddsFile.write(alpha_data[4:6])
                        ddsFile.write(alpha_data[2:4])
                        ddsFile.write(alpha_data[0:2])
                        ddsFile.write(color0)
                        ddsFile.write(color1)
                        write_reversed(codes, ddsFile)
                case "DXT5":
                    for i in range(0, len(dataBuffer)//16):
                        offs = i*16
                        alpha0 = dataBuffer[offs:offs+1]
                        alpha1 = dataBuffer[offs+1:offs+2]
                        color0 = dataBuffer[offs+8:offs+10]
                        color1 = dataBuffer[offs+10:offs+12]
                        codes = dataBuffer[offs+12:offs+16]
                        pixels = [
                            [0,0,0,0],
                            [0,0,0,0],
                            [0,0,0,0],
                            [0,0,0,0],
                        ]
                        alpha_mask = bitarray('000000000000000000000000000000000000000000000111')
                        alpha_data_bits = bitarray()
                        alpha_data_bits.frombytes(bytearray(dataBuffer[offs+2:offs+8])[::-1])
                        shift = 0
                        
                        for y in range(0, 4):
                            for x in range(0, 4):
                                pixels[y][x] = int.from_bytes(alpha_data_bits&alpha_mask, 'big', signed=False) >> shift
                                shift += 3
                                alpha_mask = alpha_mask << 3
                        alpha_data = bitarray('000000000000000000000000000000000000000000000000')
                        shift = 0
                        for y in range(0, 4):
                            for x in range(0, 4):
                                alpha_data |= bitarray_util.int2ba(pixels[4 - y - 1][x], len(alpha_data)) << shift
                                shift += 3
                        alpha_data = bytes(alpha_data)
                        ddsFile.write(alpha0)
                        ddsFile.write(alpha1)
                        write_reversed(alpha_data, ddsFile)
                        ddsFile.write(color0)
                        ddsFile.write(color1)
                        write_reversed(codes, ddsFile)
                case "ARGB8":
                    w = ddsHeader.dwWidth
                    h = ddsHeader.dwHeight
                    pixelBlockSize = ddsHeader.ddspf.dwRGBBitCount // 8
                    newbuf = bytearray(w * h * pixelBlockSize)
                    Image_MortonOrder(dataBuffer, newbuf, ddsHeader.dwWidth, ddsHeader.dwHeight, pixelBlockSize, 1, 0)
                    ddsFile.write(newbuf)
                case _:
                    print(f"FORMAT UNSUPPORTED FOR REARRANGING: {textureInfo.textureFormat} {phyrePath}")
                    ddsFile.write(dataBuffer)
    

directory = Path("ch01_00")
directory_out = Path("out")
extension = "*.dds"

files = [file for file in directory.glob(extension) if file.is_file()]
for f in files:
    (directory_out / f).parent.mkdir(parents=True, exist_ok=True)
    convertPhyre2DDS(f, directory_out / f)

